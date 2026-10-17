import { afterEach, describe, expect, it, vi } from 'vitest';
import { IDBFactory } from 'fake-indexeddb';
import { newStoredEntry, type StoredEntry } from './queue-entries';
import { createQueueStorage, MemoryQueueStorage } from './queue-storage';
import type { SessionLockManager } from './session-transition';
import { applied, deferred, settle, type Deferred } from './test-helpers';
import { withQueueLock, WriteQueue, type QueueHost } from './write-queue';
import type { Op, OpResponse, SentOp } from './types';

const NOW = new Date('2026-10-16T12:00:00.000Z');
const DAY = 24 * 60 * 60 * 1000;
const op = (listUid: string): Op => ({ type: 'list.delete', list_uid: listUid });

/** A fake server: each `sendOp` waits until the test answers it. */
function fakeSender() {
	const calls: { op: SentOp; answer: Deferred<OpResponse> }[] = [];
	return {
		calls,
		sendOp: vi.fn((_slug: string, sent: SentOp) => {
			const answer = deferred<OpResponse>();
			calls.push({ op: sent, answer });
			return answer.promise;
		})
	};
}

function fakeHost(): QueueHost {
	return {
		opQueued: vi.fn(),
		opSending: vi.fn(),
		opSettled: vi.fn(),
		opFailed: vi.fn(),
		opUnanswered: vi.fn(),
		authRequired: vi.fn(),
		opLoaded: vi.fn(),
		opDiscarded: vi.fn(),
		opsRewritten: vi.fn(),
		knownSeq: vi.fn(() => undefined)
	};
}

/** IndexedDB works through timers, so these tests wait for a condition. */
async function until(check: () => boolean | Promise<boolean>, label: string): Promise<void> {
	for (let round = 0; round < 1000; round += 1) {
		if (await check()) return;
		await new Promise((resolve) => setTimeout(resolve, 1));
	}
	throw new Error(`Timed out waiting for ${label}`);
}

const opIds = (entries: readonly StoredEntry[]): string[] => entries.map((entry) => entry.opId);

/** One fresh IndexedDB per test, so tests never see each other's ops. */
function freshFactory(): IDBFactory {
	return new IDBFactory();
}

function queueOn(
	factory: IDBFactory,
	key: string,
	sender: ReturnType<typeof fakeSender>,
	options: { host?: QueueHost; now?: () => Date; locks?: SessionLockManager | null } = {}
): WriteQueue {
	return new WriteQueue('home', sender, options.host ?? fakeHost(), {
		storage: createQueueStorage(key, { indexedDB: factory }),
		key,
		locks: options.locks ?? null,
		retryDelays: [60_000],
		now: options.now ?? (() => NOW)
	});
}

afterEach(() => {
	vi.useRealTimers();
});

describe('queue storage in IndexedDB', () => {
	it('keeps rejections in their exact room-or-share record alongside queued ops', async () => {
		const factory = freshFactory();
		const rejection = {
			id: 1,
			code: 'changed_meanwhile',
			message: 'The item changed.',
			name: 'milk',
			op: { type: 'list.delete', list_uid: 'l1', op_id: 'rejected-1' }
		};
		const room = createQueueStorage('room:home', { indexedDB: factory });
		const other = createQueueStorage('room:other', { indexedDB: factory });
		await room.addNotSaved({ ...rejection, key: rejection.op.op_id });
		await room.add(newStoredEntry({ ...op('l2'), op_id: 'waiting-1' }, NOW.toISOString()));
		await room.setStates(['waiting-1'], 'signout');

		const reopened = createQueueStorage('room:home', { indexedDB: factory });
		expect(await reopened.readNotSaved()).toEqual([{ ...rejection, key: rejection.op.op_id }]);
		expect(await reopened.read()).toMatchObject([{ opId: 'waiting-1', state: 'signout' }]);
		expect(await other.readNotSaved()).toEqual([]);

		await reopened.removeNotSaved([rejection.op.op_id]);
		expect(await reopened.read()).toHaveLength(1);
		await reopened.clear();
		expect(await room.readNotSaved()).toEqual([]);
		expect(await room.read()).toEqual([]);
	});

	it("merges two tabs' rejections and only removes the dismissed identity", async () => {
		const factory = freshFactory();
		const a = createQueueStorage('room:home', { indexedDB: factory });
		const b = createQueueStorage('room:home', { indexedDB: factory });
		await a.readNotSaved();
		await b.readNotSaved();
		const first = { key: 'a', code: 'refused-a' };
		const second = { key: 'b', code: 'refused-b' };
		const future = { format: 2, payload: 'keep intact' };
		await a.addNotSaved(first);
		await a.addNotSaved({ ...future, key: 'future' });
		await b.addNotSaved(second);
		await a.removeNotSaved(['a']);
		// A stale tab cannot reinsert a dismissed entry through an update.
		const stale = { ...first, code: 'stale-update' };
		await b.updateNotSaved(stale);
		expect(await a.readNotSaved()).toEqual([{ ...future, key: 'future' }, second]);
		const updated = { ...second, code: 'new-answer' };
		await b.updateNotSaved(updated);
		expect(await a.readNotSaved()).toEqual([
			{ ...future, key: 'future' },
			{ ...second, code: 'new-answer' }
		]);
	});

	it('keeps ops, their op_ids and their order across a reload', async () => {
		const factory = freshFactory();
		const first = queueOn(factory, 'room:home', fakeSender());
		void first.send(op('a')).catch(() => undefined);
		void first.send(op('b')).catch(() => undefined);
		const reader = createQueueStorage('room:home', { indexedDB: factory });
		await until(async () => (await reader.read()).length === 2, 'two stored ops');
		const originalIds = first.pending.map((queued) => queued.op_id);

		// A new page: same storage, new queue.
		const sender = fakeSender();
		const reloaded = queueOn(factory, 'room:home', sender);
		await reloaded.load();
		expect(reloaded.pending.map((queued) => queued.op_id)).toEqual(originalIds);
		reloaded.resume();
		await until(() => sender.calls.length === 1, 'first op sent');
		expect(sender.calls[0].op).toMatchObject({ list_uid: 'a', op_id: originalIds[0] });
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		await until(() => sender.calls.length === 2, 'second op sent');
		expect(sender.calls[1].op).toMatchObject({ list_uid: 'b', op_id: originalIds[1] });
	});

	it('stores each op with its time, format 1 and state pending', async () => {
		const factory = freshFactory();
		const queue = queueOn(factory, 'room:home', fakeSender());
		void queue.send(op('a')).catch(() => undefined);
		const reader = createQueueStorage('room:home', { indexedDB: factory });
		await until(async () => (await reader.read()).length === 1, 'one stored op');
		const [entry] = await reader.read();
		expect(entry).toMatchObject({
			opId: queue.pending[0].op_id,
			op: { type: 'list.delete', list_uid: 'a', op_id: queue.pending[0].op_id },
			at: NOW.toISOString(),
			format: 1,
			state: 'pending'
		});
	});

	it('removes an op from storage when the server answers it', async () => {
		const factory = freshFactory();
		const sender = fakeSender();
		const queue = queueOn(factory, 'room:home', sender);
		const first = queue.send(op('a'));
		void queue.send(op('b')).catch(() => undefined);
		const reader = createQueueStorage('room:home', { indexedDB: factory });
		await until(() => sender.calls.length === 1, 'first op sent');
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		await first;
		await until(async () => (await reader.read()).length === 1, 'one op left');
		expect(await reader.read()).toMatchObject([{ op: { list_uid: 'b' } }]);
	});

	it('keeps rooms and share links apart, even with the same name', async () => {
		const factory = freshFactory();
		const room = createQueueStorage('room:home', { indexedDB: factory });
		const share = createQueueStorage('share:home', { indexedDB: factory });
		await room.add(newStoredEntry({ ...op('a'), op_id: 'op-room' }, NOW.toISOString()));
		expect(await share.read()).toEqual([]);
		expect(opIds(await room.read())).toEqual(['op-room']);
	});

	it('clears a room on dispose, so storage matches memory', async () => {
		const factory = freshFactory();
		const queue = queueOn(factory, 'room:home', fakeSender());
		const sent = queue.send(op('a'));
		const reader = createQueueStorage('room:home', { indexedDB: factory });
		await until(async () => (await reader.read()).length === 1, 'one stored op');
		queue.dispose(new Error('Closed.'));
		await expect(sent).rejects.toThrow('Closed.');
		await until(async () => (await reader.read()).length === 0, 'storage cleared');
	});

	it('keeps two rooms as two queues: each sends its own ops', async () => {
		const factory = freshFactory();
		const senderA = fakeSender();
		const senderB = fakeSender();
		const queueA = queueOn(factory, 'room:a', senderA);
		const queueB = queueOn(factory, 'room:b', senderB);
		void queueA.send(op('a1')).catch(() => undefined);
		void queueB.send(op('b1')).catch(() => undefined);
		await until(() => senderA.calls.length === 1 && senderB.calls.length === 1, 'both sent');
		expect(senderA.calls[0].op).toMatchObject({ list_uid: 'a1' });
		expect(senderB.calls[0].op).toMatchObject({ list_uid: 'b1' });
		const storageA = createQueueStorage('room:a', { indexedDB: factory });
		expect(opIds(await storageA.read())).toEqual([queueA.pending[0].op_id]);
	});

	it('falls back to memory when IndexedDB cannot open, and goes on sending', async () => {
		const broken = {
			open() {
				throw new Error('blocked');
			}
		} as unknown as IDBFactory;
		const sender = fakeSender();
		const queue = queueOn(broken, 'room:home', sender);
		const sent = queue.send(op('a'));
		await until(() => sender.calls.length === 1, 'op sent from memory');
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		await expect(sent).resolves.toMatchObject({ status: 'applied' });
	});

	it('reports memory-only storage when IndexedDB is missing', async () => {
		const storage = createQueueStorage('room:home', { indexedDB: null });
		expect(storage).toBeInstanceOf(MemoryQueueStorage);
		expect(storage.durable).toBe(false);
		let durable: boolean | null = null;
		const queue = new WriteQueue('home', fakeSender(), fakeHost(), {
			storage,
			key: 'room:home',
			onChange: (snapshot) => {
				durable = snapshot.durable;
			}
		});
		await queue.load();
		expect(durable).toBe(false);
	});
});

describe('unreadable and held entries', () => {
	it('keeps an entry from a newer format and does not send it or the ops behind it', async () => {
		const factory = freshFactory();
		const storage = createQueueStorage('room:home', { indexedDB: factory });
		await storage.add({
			opId: 'future-op',
			op: { ...op('future'), op_id: 'future-op' },
			at: NOW.toISOString(),
			format: 2,
			state: 'pending'
		});

		const sender = fakeSender();
		const host = fakeHost();
		const queue = queueOn(factory, 'room:home', sender, { host });
		await queue.load();
		queue.resume();
		void queue.send(op('later')).catch(() => undefined);
		await settle();
		await new Promise((resolve) => setTimeout(resolve, 20));

		expect(sender.calls).toHaveLength(0);
		expect(queue.waiting).toBe(2);
		expect(queue.pending.map((queued) => queued.op_id)).not.toContain('future-op');
		expect(await storage.read()).toHaveLength(2);
	});

	it('lists an op that fails validation, and discarding it lets the queue go on', async () => {
		const factory = freshFactory();
		const storage = createQueueStorage('room:home', { indexedDB: factory });
		await storage.add({
			opId: 'broken',
			op: { op_id: 'broken', type: 'item.unknown_kind' },
			at: NOW.toISOString(),
			format: 1,
			state: 'pending'
		});
		const snapshots: { unreadable: { opId: string; reason: string }[] }[] = [];
		const sender = fakeSender();
		const queue = new WriteQueue('home', sender, fakeHost(), {
			storage,
			key: 'room:home',
			now: () => NOW,
			onChange: (snapshot) => snapshots.push(snapshot)
		});
		await queue.load();
		expect(snapshots.at(-1)?.unreadable).toEqual([
			expect.objectContaining({ opId: 'broken', reason: 'invalid' })
		]);
		queue.resume();
		const sent = queue.send(op('next'));
		await settle();
		expect(sender.calls).toHaveLength(0);

		expect(queue.discard('broken')).toBe(true);
		await until(() => sender.calls.length === 1, 'next op sent after discard');
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		await expect(sent).resolves.toMatchObject({ status: 'applied' });
		expect(queue.discard('missing')).toBe(false);
	});

	it('holds ops older than 30 days until the user sends them', async () => {
		const factory = freshFactory();
		const storage = createQueueStorage('room:home', { indexedDB: factory });
		const old = new Date(NOW.getTime() - 31 * DAY).toISOString();
		const recent = new Date(NOW.getTime() - 29 * DAY).toISOString();
		await storage.add({ ...newStoredEntry({ ...op('old'), op_id: 'old-op' }, old) });
		await storage.add({ ...newStoredEntry({ ...op('recent'), op_id: 'recent-op' }, recent) });

		const sender = fakeSender();
		const queue = queueOn(factory, 'room:home', sender);
		await queue.load();
		queue.resume();
		// The old op is held; the recent one waits behind it, so nothing is sent.
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(sender.calls).toHaveLength(0);
		expect(queue.pending.map((queued) => queued.op_id)).toEqual(['old-op', 'recent-op']);

		queue.sendHeld();
		await until(() => sender.calls.length === 1, 'held op sent');
		expect(sender.calls[0].op.op_id).toBe('old-op');
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		await until(() => sender.calls.length === 2, 'recent op sent');
		expect(sender.calls[1].op.op_id).toBe('recent-op');
	});

	it('sends an op from 29 days ago without asking', async () => {
		const factory = freshFactory();
		const storage = createQueueStorage('room:home', { indexedDB: factory });
		await storage.add(
			newStoredEntry(
				{ ...op('recent'), op_id: 'recent-op' },
				new Date(NOW.getTime() - 29 * DAY).toISOString()
			)
		);
		const sender = fakeSender();
		const queue = queueOn(factory, 'room:home', sender);
		await queue.load();
		queue.resume();
		await until(() => sender.calls.length === 1, 'recent op sent');
	});

	it('holds sign-out changes across reload, then keeps the 30-day hold separate', async () => {
		const factory = freshFactory();
		const storage = createQueueStorage('room:home', { indexedDB: factory });
		const old = new Date(NOW.getTime() - 31 * DAY).toISOString();
		const recent = new Date(NOW.getTime() - DAY).toISOString();
		await storage.add(newStoredEntry({ ...op('old'), op_id: 'old-op' }, old));
		await storage.add(newStoredEntry({ ...op('recent'), op_id: 'recent-op' }, recent));

		const first = new WriteQueue('home', fakeSender(), fakeHost(), {
			storage,
			now: () => NOW
		});
		await first.load();
		await first.holdForSignOut();
		expect((await storage.read()).map((entry) => entry.state)).toEqual(['signout', 'signout']);

		const sender = fakeSender();
		const returned = new WriteQueue('home', sender, fakeHost(), {
			storage: createQueueStorage('room:home', { indexedDB: factory }),
			now: () => NOW
		});
		await returned.load();
		returned.resume();
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(sender.calls).toHaveLength(0);
		expect(returned.waiting).toBe(2);

		returned.sendAfterSignIn();
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(sender.calls).toHaveLength(0);
		expect((await storage.read()).map((entry) => entry.state)).toEqual(['pending', 'pending']);

		returned.sendHeld();
		await until(() => sender.calls.length === 1, 'old change sent after its own approval');
		expect(sender.calls[0].op.op_id).toBe('old-op');
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		await until(() => sender.calls.length === 2, 'recent change sent after old one');
		expect(sender.calls[1].op.op_id).toBe('recent-op');
	});

	it('reports held ops with their time', async () => {
		const factory = freshFactory();
		const storage = createQueueStorage('room:home', { indexedDB: factory });
		const old = new Date(NOW.getTime() - 40 * DAY).toISOString();
		await storage.add(newStoredEntry({ ...op('old'), op_id: 'old-op' }, old));
		let held: { opId: string; at: string | null }[] = [];
		const queue = new WriteQueue('home', fakeSender(), fakeHost(), {
			storage,
			key: 'room:home',
			now: () => NOW,
			onChange: (snapshot) => {
				held = snapshot.held;
			}
		});
		await queue.load();
		expect(held).toEqual([expect.objectContaining({ opId: 'old-op', at: old })]);
	});
});

describe('the per-room lock', () => {
	it('names the lock after the room, or runs without one', async () => {
		const requested: string[] = [];
		const locks = {
			request: (name: string, _options: unknown, callback: () => unknown) => {
				requested.push(name);
				return Promise.resolve(callback());
			}
		} as unknown as SessionLockManager;
		await expect(withQueueLock('room:home', async () => 7, locks)).resolves.toBe(7);
		expect(requested).toEqual(['listr:queue:room%3Ahome']);
		await expect(withQueueLock('room:home', async () => 8, null)).resolves.toBe(8);
	});

	it('lets only one queue send a room at a time', async () => {
		const locks = navigator.locks as SessionLockManager;
		const key = 'room:lock-test';
		const senderA = fakeSender();
		const senderB = fakeSender();
		const queueA = new WriteQueue('home', senderA, fakeHost(), { key, locks, now: () => NOW });
		const queueB = new WriteQueue('home', senderB, fakeHost(), { key, locks, now: () => NOW });

		void queueA.send(op('a')).catch(() => undefined);
		await until(() => senderA.calls.length === 1, 'tab A sends');
		void queueB.send(op('b')).catch(() => undefined);
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(senderB.calls).toHaveLength(0);

		senderA.calls[0].answer.resolve(applied(senderA.calls[0].op, 1));
		await until(() => senderB.calls.length === 1, 'tab B sends after A');
		expect(senderB.calls[0].op).toMatchObject({ list_uid: 'b' });
	});
});
