import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { closeRoom, openRoom, RoomHandle, type RoomApi } from './index';
import {
	applied,
	deferred,
	FakeEventSource,
	makeFeed,
	makeItem,
	makeList,
	ROOM,
	settle,
	type Deferred
} from './test-helpers';
import { ApiError } from './types';
import type { Feed, OpResponse, SentOp } from './types';

const list = makeList({ uid: 'list-a' });
const milk = makeItem(list.uid, { uid: 'item-milk', name: 'milk', quantity: 2, tags: ['Lidl'] });

/** A scripted server: tests queue feeds and answer each op by hand. */
function fakeApi() {
	const feeds: Feed[] = [makeFeed({ seq: 5, full: true, lists: [list], items: [milk] })];
	const ops: { op: SentOp; answer: Deferred<OpResponse> }[] = [];
	const api = {
		changes: vi.fn(async (_slug: string, since: number) => {
			const feed = feeds.shift();
			return feed ?? makeFeed({ seq: since });
		}),
		sendOp: vi.fn((_slug: string, op: SentOp) => {
			const answer = deferred<OpResponse>();
			ops.push({ op, answer });
			return answer.promise;
		}),
		login: vi.fn(async () => ROOM),
		logout: vi.fn(async () => undefined),
		whoAmI: vi.fn(async () => ROOM),
		changePassword: vi.fn(async () => ROOM),
		deleteRoom: vi.fn(async (): Promise<void> => undefined),
		shareLink: vi.fn(async () => ({ token: 'share-token' })),
		resetShareLink: vi.fn(async () => ({ token: 'new-token' })),
		eventsUrl: (slug: string) => `/api/v1/rooms/${slug}/events`
	} satisfies RoomApi;
	return { api, feeds, ops };
}

async function opened() {
	const server = fakeApi();
	const room = new RoomHandle(ROOM.slug, {
		api: server.api,
		snapshotStore: null,
		sessionLocks: null,
		createEventSource: (url) => new FakeEventSource(url),
		visibility: null,
		online: null
	});
	room.retain();
	await settle();
	return { room, store: room.store, ...server };
}

describe('RoomHandle', () => {
	beforeEach(() => {
		FakeEventSource.reset();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('loads the room and starts live updates', async () => {
		const { store } = await opened();
		expect(store.status).toBe('ready');
		expect(store.lists).toEqual([list]);
		expect(FakeEventSource.last.url).toBe('/api/v1/rooms/home-ab12cd/events');
	});

	it('shows a change at once and settles after the feed', async () => {
		const { room, store, ops, feeds } = await opened();
		const result = room.setDone(milk, true);
		expect(store.item(milk.uid)?.done).toBe(true);
		await settle();
		expect(ops[0].op).toMatchObject({
			type: 'item.set_done',
			list_uid: list.uid,
			item_uid: milk.uid,
			done: true
		});

		const serverMilk = { ...milk, done: true, completed_at: '2026-10-03T10:00:00.000000Z' };
		feeds.push(makeFeed({ seq: 6, items: [serverMilk] }));
		ops[0].answer.resolve(applied(ops[0].op, 6));

		expect(await result).toEqual({ ok: true, result: {} });
		expect(store.seq).toBe(6);
		expect(store.pendingOps).toHaveLength(0);
		expect(store.item(milk.uid)).toEqual(serverMilk);
	});

	it.each([
		['quantity_delta', 'quantity', 3],
		['toggle_tag', 'tags', []]
	] as const)(
		'shows %s once when the live update comes before the answer',
		async (_name, field, expected) => {
			const { room, store, ops, feeds, api } = await opened();
			const result =
				field === 'quantity' ? room.changeQuantity(milk, 1) : room.toggleItemTag(milk, 'Lidl');
			const seen = [store.item(milk.uid)?.[field]];
			await settle();
			expect(ops).toHaveLength(1);

			// The server commits, wakes the stream, then answers the op.
			const serverMilk = { ...milk, [field]: expected, changed_seq: 6 };
			feeds.push(makeFeed({ seq: 6, items: [serverMilk] }));
			FakeEventSource.last.open();
			FakeEventSource.last.seq(6);
			await settle();
			seen.push(store.item(milk.uid)?.[field]);
			expect(api.changes).toHaveBeenCalledTimes(1); // held until the answer

			ops[0].answer.resolve(applied(ops[0].op, 6));
			await settle();
			seen.push(store.item(milk.uid)?.[field]);
			expect((await result).ok).toBe(true);

			expect(seen).toEqual([expected, expected, expected]);
			expect(store.item(milk.uid)).toEqual(serverMilk);
			expect(store.pendingOps).toHaveLength(0);
			expect(api.changes).toHaveBeenCalledTimes(2);
		}
	);

	it('reverts a rejected change and surfaces its message', async () => {
		const { room, store, ops } = await opened();
		const result = room.changeQuantity(milk, 1);
		expect(store.item(milk.uid)?.quantity).toBe(3);
		await settle();

		ops[0].answer.resolve({
			op_id: ops[0].op.op_id,
			status: 'rejected',
			code: 'item_not_found',
			message: 'The item is no longer available.',
			seq: 5
		});
		expect(await result).toEqual({
			ok: false,
			code: 'item_not_found',
			message: 'The item is no longer available.'
		});
		expect(store.item(milk.uid)?.quantity).toBe(2);
		expect(store.notice?.message).toBe('The item is no longer available.');
	});

	it('creates lists and items with client uids and returns the result once the data is in', async () => {
		const { room, store, ops, feeds } = await opened();
		const created = room.createList('Hardware');
		await settle();
		const op = ops[0].op;
		expect(op).toMatchObject({ type: 'list.create', name: 'Hardware' });
		const uid = (op as { uid: string }).uid;
		expect(uid).toMatch(/^[0-9a-f-]{36}$/);

		const hardware = makeList({ uid, name: 'Hardware', slug: 'hardware-1' });
		feeds.push(makeFeed({ seq: 6, lists: [hardware] }));
		ops[0].answer.resolve(applied(op, 6, { list_uid: uid, slug: 'hardware-1', created: true }));

		const result = await created;
		expect(result).toEqual({
			ok: true,
			result: { list_uid: uid, slug: 'hardware-1', created: true }
		});
		expect(store.listBySlug('hardware-1')).toEqual(hardware);
	});

	it('keeps a deleted item so undo can restore it', async () => {
		const { room, store, ops, feeds } = await opened();
		const doneMilk = { ...milk, done: true, completed_at: '2026-10-01T08:00:00.000000Z' };
		feeds.push(makeFeed({ seq: 6, items: [doneMilk] }));
		await store.refresh();

		const deleted = room.deleteItem(store.item(milk.uid)!);
		expect(store.itemsOf(list.uid)).toEqual([]);
		await settle();
		feeds.push(makeFeed({ seq: 7, deletions: [{ kind: 'item', uid: milk.uid }] }));
		ops[0].answer.resolve(applied(ops[0].op, 7));
		expect((await deleted).ok).toBe(true);

		const restored = room.restoreItem(milk.uid);
		await settle();
		const restoreOp = ops[1].op;
		expect(restoreOp).toMatchObject({
			type: 'item.restore',
			list_uid: list.uid,
			name: 'milk',
			done: true,
			tags: ['Lidl'],
			description: '',
			quantity: 2,
			completed_at: '2026-10-01T08:00:00.000000Z'
		});
		const newUid = (restoreOp as { uid: string }).uid;
		expect(newUid).not.toBe(milk.uid);

		feeds.push(makeFeed({ seq: 8, items: [{ ...doneMilk, uid: newUid }] }));
		ops[1].answer.resolve(applied(restoreOp, 8, { item_uid: newUid }));
		expect(await restored).toEqual({ ok: true, result: { item_uid: newUid } });
		expect(store.itemsOf(list.uid).map((item) => item.uid)).toEqual([newUid]);
		expect((await room.restoreItem(milk.uid)).ok).toBe(false);
	});

	it('pauses writes on 401 and sends them after sign-in', async () => {
		const { room, store, ops, api } = await opened();
		const result = room.addListTag(list, 'Coop');
		await settle();
		ops[0].answer.reject(new ApiError(401, 'not_authenticated', 'Sign in to this room.'));
		await settle();
		expect(store.status).toBe('auth_required');
		expect(store.lists).toEqual([]);
		expect(room.queuedOps).toHaveLength(1);

		expect(await room.login('secret')).toEqual({ ok: true, result: ROOM });
		expect(api.login).toHaveBeenCalledWith(ROOM.slug, 'secret');
		expect(store.status).toBe('ready');
		await settle();
		expect(ops).toHaveLength(2);
		expect(ops[1].op).toEqual(ops[0].op);
		ops[1].answer.resolve(applied(ops[1].op, 5));
		expect((await result).ok).toBe(true);
	});

	it('reads the changes when the events stream says so', async () => {
		const { store, feeds } = await opened();
		const bread = makeItem(list.uid, { name: 'bread' });
		feeds.push(makeFeed({ seq: 9, items: [bread] }));
		FakeEventSource.last.open();
		FakeEventSource.last.seq(9);
		await settle();
		expect(store.seq).toBe(9);
		expect(store.item(bread.uid)).toEqual(bread);
	});

	it('clears the view and pauses pending writes on local sign-out', async () => {
		const { room, store } = await opened();
		const pending = room.setDone(milk, true);
		let completed = false;
		void pending.then(() => (completed = true));
		await settle();
		const original = room.queuedOps[0];
		room.signedOut();
		await settle();
		expect(completed).toBe(false);
		expect(room.queuedOps).toEqual([original]);
		expect(store.lists).toEqual([]);
		expect(store.status).toBe('auth_required');
		expect(FakeEventSource.last.closed).toBe(true);
	});
});

describe('room management', () => {
	beforeEach(() => {
		FakeEventSource.reset();
	});

	it('renames the room with an op and resolves once the feed has the name', async () => {
		const { room, store, ops, feeds } = await opened();
		const result = room.renameRoom('Cabin');
		await settle();
		expect(ops[0].op).toMatchObject({ type: 'room.rename', name: 'Cabin' });
		expect(ops[0].op.op_id).toEqual(expect.any(String));

		feeds.push(makeFeed({ seq: 6, room: { ...ROOM, name: 'Cabin' } }));
		ops[0].answer.resolve(applied(ops[0].op, 6));
		expect(await result).toEqual({ ok: true, result: {} });
		expect(store.room?.name).toBe('Cabin');
	});

	it('reports a rejected room rename', async () => {
		const { room, store, ops } = await opened();
		const result = room.renameRoom(' ');
		await settle();
		ops[0].answer.resolve({
			op_id: ops[0].op.op_id,
			status: 'rejected',
			code: 'invalid_name',
			message: 'Name cannot be empty',
			seq: 5
		});
		expect(await result).toEqual({
			ok: false,
			code: 'invalid_name',
			message: 'Name cannot be empty'
		});
		expect(store.room?.name).toBe('Home');
	});

	it('changes the password and stays signed in when its own stream is revoked', async () => {
		const { room, store, api } = await opened();
		const answer = deferred<typeof ROOM>();
		api.changePassword.mockReturnValueOnce(answer.promise);
		const stream = FakeEventSource.last;
		stream.open();

		const result = room.changePassword('old', 'new');
		expect(api.changePassword).toHaveBeenCalledWith(ROOM.slug, 'old', 'new');
		// The server revokes the old token before this browser has the new cookie.
		stream.revoked();
		await settle();
		expect(api.whoAmI).toHaveBeenCalledTimes(1); // initial access validation only

		answer.resolve(ROOM);
		expect(await result).toEqual({ ok: true, result: ROOM });
		await settle();
		expect(api.whoAmI).toHaveBeenCalledTimes(3);
		expect(store.status).toBe('ready');
	});

	it('reports a wrong current password and keeps the room', async () => {
		const { room, store, api } = await opened();
		api.changePassword.mockRejectedValueOnce(
			new ApiError(403, 'wrong_password', 'Incorrect current password')
		);
		expect(await room.changePassword('bad', 'new')).toEqual({
			ok: false,
			code: 'wrong_password',
			message: 'Incorrect current password'
		});
		expect(store.status).toBe('ready');
		expect(store.lists).toEqual([list]);
	});

	it('settles queued actions only after confirmed room deletion', async () => {
		const { room, store, api, ops } = await opened();
		const pending = room.setDone(milk, true);
		await settle();
		api.deleteRoom.mockRejectedValueOnce(new ApiError(403, 'wrong_password', 'Incorrect password'));
		expect((await room.deleteRoom('bad')).ok).toBe(false);
		expect(room.queuedOps).toHaveLength(1);
		expect(await room.deleteRoom('secret')).toEqual({ ok: true, result: {} });
		expect(api.deleteRoom).toHaveBeenCalledWith(ROOM.slug, 'secret');
		expect(await pending).toMatchObject({ ok: false, code: 'session_changed' });
		expect(room.queuedOps).toEqual([]);
		ops[0].answer.resolve(applied(ops[0].op, 6));
		await settle();
		expect(store.notice).toBeNull();
		expect(store.lists).toEqual([]);
		// No password prompt flashes while the page leaves.
		expect(store.status).toBe('loading');
		expect(FakeEventSource.last.closed).toBe(true);
	});

	it('keeps the room when the delete password is wrong', async () => {
		const { room, store, api } = await opened();
		api.deleteRoom.mockRejectedValueOnce(new ApiError(403, 'wrong_password', 'Incorrect password'));
		expect(await room.deleteRoom('bad')).toEqual({
			ok: false,
			code: 'wrong_password',
			message: 'Incorrect password'
		});
		expect(store.status).toBe('ready');
		expect(store.lists).toEqual([list]);
		expect(FakeEventSource.last.closed).toBe(false);
	});

	it('opens a deleted room afresh', async () => {
		const { api } = fakeApi();
		const options = {
			api,
			snapshotStore: null,
			sessionLocks: null,
			createEventSource: (url: string) => new FakeEventSource(url),
			visibility: null,
			online: null
		};
		const first = openRoom('deleted-room', options);
		await settle();
		expect((await first.deleteRoom('secret')).ok).toBe(true);
		closeRoom(first);
		const again = openRoom('deleted-room', options);
		expect(again).not.toBe(first);
		closeRoom(again);
	});
});

describe('share links (room members)', () => {
	beforeEach(() => {
		FakeEventSource.reset();
	});

	it('reads the share link of a list', async () => {
		const { room, api } = await opened();
		expect(await room.shareLink(list)).toEqual({ ok: true, result: { token: 'share-token' } });
		expect(api.shareLink).toHaveBeenCalledWith(ROOM.slug, list.uid);
	});

	it('resets the share link and reports a failure', async () => {
		const { room, api } = await opened();
		expect(await room.resetShareLink(list)).toEqual({ ok: true, result: { token: 'new-token' } });
		expect(api.resetShareLink).toHaveBeenCalledWith(ROOM.slug, list.uid);

		api.resetShareLink.mockRejectedValueOnce(
			new ApiError(404, 'list_unavailable', 'The list is no longer available.')
		);
		expect(await room.resetShareLink(list)).toEqual({
			ok: false,
			code: 'list_unavailable',
			message: 'The list is no longer available.'
		});
	});
});

describe('openRoom / closeRoom', () => {
	it('shares one room per slug and stops live updates when the last user leaves', async () => {
		FakeEventSource.reset();
		const { api } = fakeApi();
		const options = {
			api,
			snapshotStore: null,
			sessionLocks: null,
			createEventSource: (url: string) => new FakeEventSource(url),
			visibility: null,
			online: null
		};
		const first = openRoom('shared-room', options);
		const second = openRoom('shared-room', options);
		await settle();
		expect(second).toBe(first);
		expect(FakeEventSource.instances).toHaveLength(1);

		closeRoom(first);
		expect(FakeEventSource.last.closed).toBe(false);
		closeRoom(second);
		expect(FakeEventSource.last.closed).toBe(true);

		// Opened again: the cached data stays and live updates restart.
		await settle();
		expect(openRoom('shared-room')).toBe(first);
		await settle();
		expect(FakeEventSource.instances).toHaveLength(2);
		closeRoom(first);
	});
});
