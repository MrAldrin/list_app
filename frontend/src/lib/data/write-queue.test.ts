import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { compat, INCOMPATIBLE_CODE, resetCompat } from './compat.svelte';
import { applied, deferred, settle, type Deferred } from './test-helpers';
import { ApiError, NetworkError } from './types';
import type { Op, OpResponse, SentOp } from './types';
import { MemoryQueueStorage } from './queue-storage';
import { newStoredEntry } from './queue-entries';
import { WriteQueue, type QueueHost } from './write-queue';

const DELETE: Op = { type: 'list.delete', list_uid: 'l1' };
const op = (listUid: string): Op => ({ type: 'list.delete', list_uid: listUid });

/** A fake server: each `sendOp` call waits until the test answers it. */
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

function fakeHost() {
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
	} satisfies QueueHost;
}

describe('WriteQueue', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('adds an op_id and sends ops in order, one at a time', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		const second = queue.send(op('b'));
		await settle();
		expect(sender.calls).toHaveLength(1);
		expect(sender.calls[0].op).toMatchObject({ type: 'list.delete', list_uid: 'a' });
		expect(sender.calls[0].op.op_id).toMatch(/^[0-9a-f-]{36}$/);
		expect(host.opQueued).toHaveBeenCalledTimes(2);

		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		expect(await first).toMatchObject({ status: 'applied', seq: 1 });
		await settle();
		expect(sender.calls).toHaveLength(2);
		expect(sender.calls[1].op).toMatchObject({ list_uid: 'b' });
		expect(sender.calls[1].op.op_id).not.toBe(sender.calls[0].op.op_id);

		sender.calls[1].answer.resolve(applied(sender.calls[1].op, 2));
		await second;
		expect(queue.pending).toHaveLength(0);
	});

	it('tells the host when an answer is open and when it comes', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const sent = queue.send(DELETE);
		await settle();
		expect(host.opSending).toHaveBeenCalledWith(sender.calls[0].op);
		expect(host.opSettled).not.toHaveBeenCalled();

		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 6));
		await sent;
		expect(host.opSettled).toHaveBeenCalledWith(sender.calls[0].op, applied(sender.calls[0].op, 6));
	});

	it('retries the same op_id after a network error or 503, keeping the order', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host, { retryDelays: [1000, 5000] });

		const first = queue.send(op('a'));
		void queue.send(op('b'));
		await settle();
		sender.calls[0].answer.reject(new NetworkError());
		await settle();
		expect(sender.calls).toHaveLength(1);
		expect(host.opUnanswered).toHaveBeenCalledWith(sender.calls[0].op, true);

		await vi.advanceTimersByTimeAsync(1000);
		expect(sender.calls).toHaveLength(2);
		expect(sender.calls[1].op).toEqual(sender.calls[0].op);

		sender.calls[1].answer.reject(new ApiError(503, 'unavailable', 'busy'));
		await vi.advanceTimersByTimeAsync(4999);
		expect(sender.calls).toHaveLength(2);
		await vi.advanceTimersByTimeAsync(1);
		expect(sender.calls).toHaveLength(3);
		expect(sender.calls[2].op.op_id).toBe(sender.calls[0].op.op_id);

		sender.calls[2].answer.resolve(applied(sender.calls[2].op, 1));
		await first;
		await settle();
		expect(sender.calls[3].op).toMatchObject({ list_uid: 'b' });
		expect(host.opFailed).not.toHaveBeenCalled();
	});

	it('retries at once on retryNow', async () => {
		const sender = fakeSender();
		const queue = new WriteQueue('home', sender, fakeHost(), { retryDelays: [30_000] });

		void queue.send(DELETE);
		await settle();
		sender.calls[0].answer.reject(new NetworkError());
		await settle();
		queue.retryNow();
		await settle();
		expect(sender.calls).toHaveLength(2);
	});

	it('pauses on 401 and sends the waiting ops after resume', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		void queue.send(op('b'));
		await settle();
		sender.calls[0].answer.reject(new ApiError(401, 'not_authenticated', 'Sign in.'));
		await settle();

		expect(host.authRequired).toHaveBeenCalledTimes(1);
		expect(host.opUnanswered).toHaveBeenCalledWith(sender.calls[0].op, false);
		expect(queue.paused).toBe(true);
		expect(queue.pending).toHaveLength(2);
		void queue.send(op('c'));
		await vi.advanceTimersByTimeAsync(60_000);
		expect(sender.calls).toHaveLength(1);

		queue.resume();
		await settle();
		expect(sender.calls).toHaveLength(2);
		expect(sender.calls[1].op).toEqual(sender.calls[0].op);
		sender.calls[1].answer.resolve(applied(sender.calls[1].op, 1));
		await first;
		await settle();
		expect(sender.calls[2].op).toMatchObject({ list_uid: 'b' });
	});

	it.each([403, 409, 415, 422, 500])('fails the op on %s and goes on', async (status) => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		const second = queue.send(op('b'));
		await settle();
		const error = new ApiError(status, 'invalid_request', 'Nope.');
		sender.calls[0].answer.reject(error);

		await expect(first).rejects.toBe(error);
		expect(host.opFailed).toHaveBeenCalledWith(sender.calls[0].op, error);
		await settle();
		expect(sender.calls[1].op).toMatchObject({ list_uid: 'b' });
		sender.calls[1].answer.resolve(applied(sender.calls[1].op, 1));
		await expect(second).resolves.toMatchObject({ status: 'applied' });
	});

	it('resolves rejected answers and goes on', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		await settle();
		const rejected: OpResponse = {
			op_id: sender.calls[0].op.op_id,
			status: 'rejected',
			code: 'list_unavailable',
			message: 'The list is no longer available.',
			seq: 0
		};
		sender.calls[0].answer.resolve(rejected);
		expect(await first).toEqual(rejected);
		expect(host.opSettled).toHaveBeenCalledWith(sender.calls[0].op, rejected);
	});

	it('rejects every queued op on dispose', async () => {
		const sender = fakeSender();
		const queue = new WriteQueue('home', sender, fakeHost());
		const first = queue.send(op('a'));
		const second = queue.send(op('b'));
		const reason = new Error('Signed out.');

		queue.dispose(reason);
		await expect(first).rejects.toBe(reason);
		await expect(second).rejects.toBe(reason);
		expect(queue.pending).toHaveLength(0);
		await expect(queue.send(op('c'))).rejects.toThrow('closed');
	});

	describe('after a new server version is seen', () => {
		afterEach(resetCompat);

		it('stops retrying but keeps the op and its op_id', async () => {
			const sender = fakeSender();
			const host = fakeHost();
			const queue = new WriteQueue('home', sender, host, { retryDelays: [1_000] });

			void queue.send(op('a')).catch(() => undefined);
			await settle();
			const opId = sender.calls[0].op.op_id;
			compat.incompatible = true;
			sender.calls[0].answer.reject(new NetworkError());
			await settle();
			await vi.advanceTimersByTimeAsync(60_000);

			expect(sender.calls).toHaveLength(1);
			expect(queue.pending.map((queued) => queued.op_id)).toEqual([opId]);
			expect(host.opFailed).not.toHaveBeenCalled();
		});

		it('sends nothing more, and keeps every queued op', async () => {
			const sender = fakeSender();
			const host = fakeHost();
			const queue = new WriteQueue('home', sender, host);

			void queue.send(op('a')).catch(() => undefined);
			void queue.send(op('b')).catch(() => undefined);
			await settle();
			compat.incompatible = true;
			sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
			await settle();
			queue.resume();
			await settle();

			expect(sender.calls).toHaveLength(1);
			expect(queue.pending).toHaveLength(1);
			expect(queue.pending[0]).toMatchObject({ list_uid: 'b' });
		});

		it('reports its waiting ops, so the banner can warn before a reload', async () => {
			resetCompat();
			const sender = fakeSender();
			const queue = new WriteQueue('home', sender, fakeHost());

			void queue.send(op('a')).catch(() => undefined);
			void queue.send(op('b')).catch(() => undefined);
			await settle();
			expect(compat.waitingWrites).toBe(2);

			sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
			await settle();
			expect(compat.waitingWrites).toBe(1);

			queue.dispose();
			expect(compat.waitingWrites).toBe(0);
		});

		it('keeps an op the client refused to send', async () => {
			const sender = fakeSender();
			const host = fakeHost();
			const queue = new WriteQueue('home', sender, host);

			void queue.send(op('a')).catch(() => undefined);
			await settle();
			const opId = sender.calls[0].op.op_id;
			sender.calls[0].answer.reject(new ApiError(0, INCOMPATIBLE_CODE, 'New version'));
			await settle();

			expect(host.opFailed).not.toHaveBeenCalled();
			expect(queue.pending.map((queued) => queued.op_id)).toEqual([opId]);
		});
	});

	describe('offline edits (6.2d)', () => {
		it('rewrites a later queued op in storage and tells the host, after an answer', async () => {
			const sender = fakeSender();
			const host = fakeHost();
			const storage = new MemoryQueueStorage();
			const queue = new WriteQueue('home', sender, host, { storage });
			const tick: Op = {
				type: 'item.set_done',
				list_uid: 'l1',
				item_uid: 'milk',
				done: true,
				base_seq: 5
			};
			const edit: Op = {
				type: 'item.edit',
				list_uid: 'l1',
				item_uid: 'milk',
				name: 'milk',
				description: 'cold',
				base_seq: 5
			};
			const first = queue.send(tick);
			void queue.send(edit);
			await settle();
			const tickSent = sender.calls[0].op;
			sender.calls[0].answer.resolve(applied(tickSent, 7, { changed_seq: 7 }));
			await first;
			await settle();

			const editSent = sender.calls[1].op;
			expect(editSent).toMatchObject({ type: 'item.edit', base_seq: 7 });
			expect(host.opsRewritten).toHaveBeenCalledWith([
				{ opId: editSent.op_id, op: { ...editSent, base_seq: 7 } }
			]);
			const stored = await storage.read();
			expect(stored.map((entry) => entry.op)).toEqual([{ ...editSent, base_seq: 7 }]);
			sender.calls[1].answer.resolve(applied(editSent, 8));
		});

		it('hands loaded ops to the host with their stored time', async () => {
			const storage = new MemoryQueueStorage();
			const stored: SentOp = { ...DELETE, op_id: 'stored-1' } as SentOp;
			await storage.add(newStoredEntry(stored, '2026-10-01T10:00:00.000Z'));
			const host = fakeHost();
			const queue = new WriteQueue('home', fakeSender(), host, { storage });
			await queue.load();
			expect(host.opLoaded).toHaveBeenCalledWith(stored, '2026-10-01T10:00:00.000Z', false);
		});

		it('tells the host when the user discards a held op', async () => {
			const storage = new MemoryQueueStorage();
			const stored: SentOp = { ...DELETE, op_id: 'old-1' } as SentOp;
			await storage.add(newStoredEntry(stored, '2026-08-01T10:00:00.000Z'));
			const host = fakeHost();
			const queue = new WriteQueue('home', fakeSender(), host, {
				storage,
				now: () => new Date('2026-10-16T10:00:00.000Z')
			});
			await queue.load();
			expect(queue.discard('old-1')).toBe(true);
			expect(host.opDiscarded).toHaveBeenCalledWith(stored);
		});
	});
});

describe('WriteQueue sent marks (6.3)', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('stores the sent flag before the request goes out', async () => {
		const storage = new MemoryQueueStorage();
		const sender = fakeSender();
		const queue = new WriteQueue('home', sender, fakeHost(), { storage });

		void queue.send(op('a'));
		await settle();
		expect(sender.calls).toHaveLength(1);
		const [entry] = await storage.read();
		expect(entry.sent).toBe(true);
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 3));
	});

	it('tells the host a loaded op may already have been sent', async () => {
		const storage = new MemoryQueueStorage();
		const sent: SentOp = { ...DELETE, op_id: 'sent-1' } as SentOp;
		const fresh: SentOp = { ...DELETE, op_id: 'fresh-1' } as SentOp;
		const at = '2026-10-01T10:00:00.000Z';
		await storage.add({ ...newStoredEntry(sent, at), sent: true });
		await storage.add(newStoredEntry(fresh, at));
		const host = fakeHost();
		const queue = new WriteQueue('home', fakeSender(), host, { storage });

		await queue.load();
		expect(host.opLoaded).toHaveBeenCalledWith(sent, at, true);
		expect(host.opLoaded).toHaveBeenCalledWith(fresh, at, false);
	});

	it('does not send an op again as a new request after a reload, and keeps its body', async () => {
		const storage = new MemoryQueueStorage();
		const sent: SentOp = { ...DELETE, op_id: 'sent-1' } as SentOp;
		await storage.add({ ...newStoredEntry(sent, '2026-10-01T10:00:00.000Z'), sent: true });
		const sender = fakeSender();
		const queue = new WriteQueue('home', sender, fakeHost(), { storage });

		await queue.load();
		queue.resume();
		await settle();
		// The stored op is retried with its own op_id.
		expect(sender.calls[0].op.op_id).toBe('sent-1');
		sender.calls[0].answer.resolve(applied(sent, 4));
	});

	it('reports a send made while the page could not write as offline', async () => {
		const host = fakeHost();
		const queue = new WriteQueue('home', fakeSender(), host, {
			storage: new MemoryQueueStorage()
		});

		void queue.send(op('a'), true);
		void queue.send(op('b'));
		expect(host.opQueued).toHaveBeenNthCalledWith(1, expect.anything(), true);
		expect(host.opQueued).toHaveBeenNthCalledWith(2, expect.anything(), false);
	});

	it('discards every waiting op that is not being sent', async () => {
		const storage = new MemoryQueueStorage();
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host, { storage });

		const first = queue.send(op('a'));
		const second = queue.send(op('b'));
		const third = queue.send(op('c'));
		await settle();
		// `a` is in flight and stays; `b` and `c` go.
		queue.discardAll();
		await expect(second).rejects.toThrow('This change was discarded.');
		await expect(third).rejects.toThrow('This change was discarded.');
		expect(host.opDiscarded).toHaveBeenCalledTimes(2);
		expect(queue.waiting).toBe(1);
		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 5));
		await first;
	});
});
