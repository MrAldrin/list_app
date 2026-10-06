import { afterEach, describe, expect, it, vi } from 'vitest';
import { IDBFactory, IDBObjectStore } from 'fake-indexeddb';
import {
	SNAPSHOT_SCHEMA_VERSION,
	createSnapshotStore,
	type RoomIdentity,
	type SnapshotClearChannel,
	type SnapshotData,
	type SnapshotIdentity
} from '#lib/data/snapshot-store.ts';

let databaseNumber = 0;
const stores: ReturnType<typeof createSnapshotStore>[] = [];

function makeStore(indexedDB = new IDBFactory()) {
	const store = createSnapshotStore({
		indexedDB,
		databaseName: `snapshot-test-${++databaseNumber}`,
		now: () => new Date('2026-10-06T12:34:56.000Z'),
		channel: null
	});
	stores.push(store);
	return { store, indexedDB };
}

function roomData(slug = 'kitchen'): SnapshotData {
	return {
		seq: 8,
		room: { slug, name: 'Kitchen' },
		lists: [
			{
				uid: 'list-1',
				slug: 'groceries',
				name: 'Groceries',
				tags: ['Market'],
				hide_done: { mode: 'age', age_days: 7, recent_count: 10 },
				changed_seq: 8
			},
			{
				uid: 'list-2',
				slug: 'hardware',
				name: 'Hardware',
				tags: [],
				hide_done: { mode: 'off', age_days: 7, recent_count: 10 },
				changed_seq: 6
			}
		],
		items: [
			{
				uid: 'item-1',
				list_uid: 'list-1',
				name: 'milk',
				done: false,
				completed_at: null,
				quantity: 1,
				description: '',
				tags: ['Market'],
				changed_seq: 8
			}
		]
	};
}

async function requestValue<T>(request: IDBRequest<T>): Promise<T> {
	return new Promise((resolve, reject) => {
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error);
	});
}

async function openDb(factory: IDBFactory, name: string): Promise<IDBDatabase> {
	return new Promise((resolve, reject) => {
		const request = factory.open(name);
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error);
	});
}

function channelPair(): [SnapshotClearChannel, SnapshotClearChannel] {
	const listeners = [
		new Set<(event: MessageEvent) => void>(),
		new Set<(event: MessageEvent) => void>()
	];
	const make = (own: number, other: number): SnapshotClearChannel => ({
		postMessage(message) {
			for (const listener of listeners[other]) listener({ data: message } as MessageEvent);
		},
		addEventListener(_type, listener) {
			listeners[own].add(listener);
		},
		removeEventListener(_type, listener) {
			listeners[own].delete(listener);
		},
		close() {
			listeners[own].clear();
		}
	});
	return [make(0, 1), make(1, 0)];
}

afterEach(() => {
	for (const store of stores.splice(0)) store.close();
	vi.restoreAllMocks();
});

describe('snapshot store', () => {
	it('round-trips validated committed room data and saved-at metadata', async () => {
		const { store } = makeStore();
		const identity: SnapshotIdentity = { kind: 'room', slug: 'kitchen' };
		const captured = await store.generation(identity);
		expect(captured.ok).toBe(true);
		if (!captured.ok) return;

		const saved = await store.save(identity, roomData(), captured.value);
		expect(saved.ok).toBe(true);
		if (!saved.ok) return;
		expect(saved.value).toMatchObject({
			schemaVersion: SNAPSHOT_SCHEMA_VERSION,
			identity,
			seq: 8,
			room: { slug: 'kitchen', name: 'Kitchen' },
			savedAt: '2026-10-06T12:34:56.000Z'
		});

		const read = await store.read(identity);
		expect(read).toEqual(saved);
	});

	it('isolates tagged room and share identities even when their identifier text matches', async () => {
		const { store } = makeStore();
		const roomIdentity: SnapshotIdentity = { kind: 'room', slug: 'same-value' };
		const shareIdentity: SnapshotIdentity = { kind: 'share', token: 'same-value' };
		const roomToken = await store.generation(roomIdentity);
		const shareToken = await store.generation(shareIdentity);
		expect(roomToken.ok && shareToken.ok).toBe(true);
		if (!roomToken.ok || !shareToken.ok) return;

		const roomSave = await store.save(
			roomIdentity,
			{ ...roomData(), room: { slug: 'same-value', name: 'Private room' } },
			roomToken.value
		);
		const shareData: SnapshotData = {
			...roomData(),
			room: { slug: 'private-room-metadata', name: 'Must not persist', admin: true } as never,
			lists: [roomData().lists[0]],
			items: roomData().items
		};
		const shareSave = await store.save(shareIdentity, shareData, shareToken.value);
		expect(roomSave.ok && shareSave.ok).toBe(true);
		if (!roomSave.ok || !shareSave.ok) return;
		expect((await store.read(roomIdentity)).ok && (await store.read(shareIdentity)).ok).toBe(true);
		const shareRead = await store.read(shareIdentity);
		expect(shareRead.ok && shareRead.value?.room).toBe(null);
		expect(shareRead.ok && shareRead.value?.lists).toHaveLength(1);
		expect(shareRead.ok && shareRead.value?.items.every((item) => item.list_uid === 'list-1')).toBe(
			true
		);
	});

	it('updates the non-authorizing last-room hint only in a successful room save and clears it on logout', async () => {
		const { store } = makeStore();
		const room: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const share: SnapshotIdentity = { kind: 'share', token: 'token-a' };
		expect(await store.lastRoom()).toEqual({ ok: true, value: null });
		const roomToken = await store.generation(room);
		const shareToken = await store.generation(share);
		if (!roomToken.ok || !shareToken.ok) throw new Error('generation unavailable');
		expect(await store.lastRoom()).toEqual({ ok: true, value: null });
		expect(
			await store.save(share, { ...roomData(), lists: [roomData().lists[0]] }, shareToken.value)
		).toMatchObject({ ok: true });
		expect(await store.lastRoom()).toEqual({ ok: true, value: null });
		expect(await store.save(room, { ...roomData(), seq: -1 }, roomToken.value)).toEqual({
			ok: false,
			reason: 'invalid_snapshot'
		});
		expect(await store.lastRoom()).toEqual({ ok: true, value: null });
		expect(await store.save(room, roomData(), roomToken.value)).toMatchObject({ ok: true });
		expect(await store.lastRoom()).toEqual({ ok: true, value: 'kitchen' });
		expect(await store.localSignOut(room)).toEqual({ ok: true, value: undefined });
		expect(await store.lastRoom()).toEqual({ ok: true, value: null });
	});

	it('rejects invalid and multi-list share snapshots without writing', async () => {
		const { store } = makeStore();
		const identity: SnapshotIdentity = { kind: 'share', token: 'token-a' };
		const captured = await store.generation(identity);
		expect(captured.ok).toBe(true);
		if (!captured.ok) return;

		const multipleLists = await store.save(identity, roomData(), captured.value);
		const wrongItems: SnapshotData = {
			...roomData(),
			lists: [roomData().lists[0]],
			items: [{ ...roomData().items[0], list_uid: 'not-this-list' }]
		};
		const invalidItems = await store.save(identity, wrongItems, captured.value);
		const badSequence = await store.save(identity, { ...roomData(), seq: -1 }, captured.value);
		expect(multipleLists).toEqual({ ok: false, reason: 'invalid_snapshot' });
		expect(invalidItems).toEqual({ ok: false, reason: 'invalid_snapshot' });
		expect(badSequence).toEqual({ ok: false, reason: 'invalid_snapshot' });
		expect(await store.read(identity)).toEqual({ ok: true, value: null });
	});

	it('clears only the requested snapshot and invalidates earlier generation tokens', async () => {
		const { store } = makeStore();
		const room: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const other: RoomIdentity = { kind: 'room', slug: 'garage' };
		const [roomToken, otherToken] = await Promise.all([
			store.generation(room),
			store.generation(other)
		]);
		expect(roomToken.ok && otherToken.ok).toBe(true);
		if (!roomToken.ok || !otherToken.ok) return;
		await store.save(room, roomData(), roomToken.value);
		await store.save(other, roomData('garage'), otherToken.value);

		const cleared = await store.clear(room);
		expect(cleared).toEqual({ ok: true, value: undefined });
		expect(await store.save(room, roomData(), roomToken.value)).toEqual({
			ok: false,
			reason: 'stale'
		});
		expect(await store.read(room)).toEqual({ ok: true, value: null });
		const otherRead = await store.read(other);
		expect(otherRead.ok && otherRead.value?.room?.slug).toBe('garage');
	});

	it('uses cross-tab clear messages only as hints; durable state controls reads', async () => {
		const factory = new IDBFactory();
		const databaseName = `snapshot-notify-${++databaseNumber}`;
		const [firstChannel, secondChannel] = channelPair();
		const first = createSnapshotStore({ indexedDB: factory, databaseName, channel: firstChannel });
		const second = createSnapshotStore({
			indexedDB: factory,
			databaseName,
			channel: secondChannel
		});
		stores.push(first, second);
		const identity: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const captured = await first.generation(identity);
		if (!captured.ok) throw new Error('generation unavailable');
		await first.save(identity, roomData(), captured.value);
		const received: string[] = [];
		second.onClear((hint) => received.push(`${hint.identity.kind}:${hint.generation}`));

		firstChannel.postMessage({ type: 'snapshot-clear', identity, generation: 999 });
		expect(received).toEqual(['room:999']);
		expect((await second.read(identity)).ok).toBe(true);

		await first.clear(identity);
		expect(received).toEqual(['room:999', 'room:1']);
		expect(await second.read(identity)).toEqual({ ok: true, value: null });
	});

	it('rejects a fetch save after another adapter clears the same identity', async () => {
		const factory = new IDBFactory();
		const databaseName = `snapshot-race-${++databaseNumber}`;
		const first = createSnapshotStore({ indexedDB: factory, databaseName, channel: null });
		const second = createSnapshotStore({ indexedDB: factory, databaseName, channel: null });
		stores.push(first, second);
		const identity: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const captured = await first.generation(identity);
		expect(captured.ok).toBe(true);
		if (!captured.ok) return;
		expect((await second.clear(identity)).ok).toBe(true);
		expect(await first.save(identity, roomData(), captured.value)).toEqual({
			ok: false,
			reason: 'stale'
		});
		expect(await second.read(identity)).toEqual({ ok: true, value: null });
	});

	it('keeps the local sign-out marker after server logout acknowledgment until explicit sign-in', async () => {
		const { store } = makeStore();
		const identity: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const beforeLogout = await store.generation(identity);
		expect(beforeLogout.ok).toBe(true);
		if (!beforeLogout.ok) return;
		await store.save(identity, roomData(), beforeLogout.value);

		expect(await store.localSignOut(identity)).toEqual({ ok: true, value: undefined });
		expect(await store.read(identity)).toEqual({ ok: false, reason: 'signed_out' });
		expect(await store.generation(identity)).toEqual({ ok: false, reason: 'signed_out' });
		expect(await store.pendingServerLogouts()).toEqual({ ok: true, value: [identity] });

		expect(await store.acknowledgeServerLogout(identity)).toEqual({ ok: true, value: undefined });
		expect(await store.pendingServerLogouts()).toEqual({ ok: true, value: [] });
		expect(await store.read(identity)).toEqual({ ok: false, reason: 'signed_out' });

		expect(await store.clearSignOutAfterSignIn(identity)).toEqual({ ok: true, value: undefined });
		expect(await store.generation(identity)).toMatchObject({ ok: true, value: { generation: 2 } });
		expect(await store.read(identity)).toEqual({ ok: true, value: null });
	});

	it('persists the sign-out guard across adapter instances and does not affect shares', async () => {
		const factory = new IDBFactory();
		const databaseName = `snapshot-marker-${++databaseNumber}`;
		const store = createSnapshotStore({ indexedDB: factory, databaseName, channel: null });
		const reopened = createSnapshotStore({ indexedDB: factory, databaseName, channel: null });
		stores.push(store, reopened);
		const room: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const share: SnapshotIdentity = { kind: 'share', token: 'token-a' };
		const shareGeneration = await store.generation(share);
		if (!shareGeneration.ok) throw new Error('share generation unavailable');
		await store.save(share, { ...roomData(), lists: [roomData().lists[0]] }, shareGeneration.value);
		await store.localSignOut(room);

		expect(await reopened.read(room)).toEqual({ ok: false, reason: 'signed_out' });
		expect(await reopened.read(share)).toMatchObject({
			ok: true,
			value: { room: null, lists: [{ uid: 'list-1' }] }
		});
	});

	it('discards only a schema-mismatched or corrupt snapshot', async () => {
		const { store, indexedDB } = makeStore();
		const roomA: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const roomB: RoomIdentity = { kind: 'room', slug: 'garage' };
		const roomC: RoomIdentity = { kind: 'room', slug: 'garden' };
		const [tokenA, tokenB, tokenC] = await Promise.all([
			store.generation(roomA),
			store.generation(roomB),
			store.generation(roomC)
		]);
		if (!tokenA.ok || !tokenB.ok || !tokenC.ok) throw new Error('generation unavailable');
		await store.save(roomA, roomData(), tokenA.value);
		await store.save(roomB, roomData('garage'), tokenB.value);
		await store.save(roomC, roomData('garden'), tokenC.value);
		const db = await openDb(indexedDB, `snapshot-test-${databaseNumber}`);
		const tx = db.transaction('snapshots', 'readwrite');
		const records = tx.objectStore('snapshots');
		const recordA = await requestValue(records.get('room:kitchen'));
		recordA.value.schemaVersion = 99;
		await requestValue(records.put(recordA));
		const recordB = await requestValue(records.get('room:garage'));
		recordB.value.items = [{ uid: 'broken' }];
		await requestValue(records.put(recordB));
		await new Promise<void>((resolve, reject) => {
			tx.oncomplete = () => resolve();
			tx.onerror = () => reject(tx.error);
		});
		db.close();

		expect(await store.read(roomA)).toEqual({ ok: true, value: null });
		expect(await store.read(roomB)).toEqual({ ok: true, value: null });
		expect(await store.read(roomC)).toMatchObject({
			ok: true,
			value: { room: { slug: 'garden' } }
		});
	});

	it('reports IndexedDB denial and quota errors as unavailable, never as successful saves', async () => {
		const denied = createSnapshotStore({
			indexedDB: {
				open: () => {
					throw new DOMException('denied', 'SecurityError');
				}
			} as unknown as IDBFactory,
			databaseName: `snapshot-denied-${++databaseNumber}`,
			channel: null
		});
		stores.push(denied);
		expect(await denied.generation({ kind: 'room', slug: 'kitchen' })).toEqual({
			ok: false,
			reason: 'unavailable'
		});

		const { store } = makeStore();
		const identity: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const token = await store.generation(identity);
		expect(token.ok).toBe(true);
		if (!token.ok) return;
		await store.save(identity, roomData(), token.value);
		const originalPut = IDBObjectStore.prototype.put;
		vi.spyOn(IDBObjectStore.prototype, 'put').mockImplementation(function (
			this: IDBObjectStore,
			...args: Parameters<IDBObjectStore['put']>
		) {
			if (this.name === 'snapshots') throw new DOMException('quota exceeded', 'QuotaExceededError');
			return originalPut.apply(this, args);
		});
		expect(await store.save(identity, roomData(), token.value)).toEqual({
			ok: false,
			reason: 'unavailable'
		});
		const retained = await store.read(identity);
		expect(retained.ok && retained.value?.seq).toBe(8);
	});

	it('rejects pending logout metadata whose key names a different room', async () => {
		const { store, indexedDB } = makeStore();
		await store.generation({ kind: 'room', slug: 'kitchen' });
		const db = await openDb(indexedDB, `snapshot-test-${databaseNumber}`);
		const tx = db.transaction('controls', 'readwrite');
		const complete = new Promise<void>((resolve, reject) => {
			tx.oncomplete = () => resolve();
			tx.onabort = () => reject(tx.error);
		});
		await requestValue(
			tx.objectStore('controls').put({
				key: 'room:kitchen',
				identity: { kind: 'room', slug: 'garage' },
				generation: 0,
				signOut: { pendingServerLogout: true }
			})
		);
		await complete;
		db.close();
		expect(await store.pendingServerLogouts()).toEqual({ ok: false, reason: 'unavailable' });
	});

	it('does not erase a fresh routing hint while cleaning a corrupt hint', async () => {
		const { store, indexedDB } = makeStore();
		const identity: RoomIdentity = { kind: 'room', slug: 'kitchen' };
		const token = await store.generation(identity);
		if (!token.ok) throw new Error('generation unavailable');
		const db = await openDb(indexedDB, `snapshot-test-${databaseNumber}`);
		const tx = db.transaction('routing', 'readwrite');
		const complete = new Promise<void>((resolve, reject) => {
			tx.oncomplete = () => resolve();
			tx.onabort = () => reject(tx.error);
		});
		await requestValue(tx.objectStore('routing').put({ key: 'last-room', slug: 123 }));
		await complete;
		db.close();
		const [, saved] = await Promise.all([
			store.lastRoom(),
			store.save(identity, roomData(), token.value)
		]);
		expect(saved.ok).toBe(true);
		expect(await store.lastRoom()).toEqual({ ok: true, value: 'kitchen' });
	});

	it('treats a malformed identity as invalid without opening IndexedDB', async () => {
		const { store } = makeStore();
		expect(await store.read({ kind: 'room', slug: '' })).toEqual({
			ok: false,
			reason: 'invalid_identity'
		});
	});
});
