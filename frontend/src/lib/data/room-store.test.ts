import { describe, expect, it, vi } from 'vitest';
import { project } from './overlay';
import { RoomStore } from './room-store.svelte';
import { deferred, makeFeed, makeItem, makeList, ROOM, settle } from './test-helpers';
import { ApiError, NetworkError } from './types';
import type { Feed, Op, SentOp } from './types';

function storeWith(changes: (slug: string, since: number) => Promise<Feed> = vi.fn()) {
	return new RoomStore(ROOM.slug, { changes });
}

let opCounter = 0;
function sent(op: Op): SentOp {
	opCounter += 1;
	return { ...op, op_id: `op-${opCounter}` } as SentOp;
}

describe('RoomStore.applyFeed', () => {
	it('replaces everything on a full feed', () => {
		const store = storeWith();
		const old = makeList({ name: 'Old' });
		store.applyFeed(makeFeed({ seq: 5, full: true, lists: [old] }));

		const list = makeList({ name: 'New' });
		const item = makeItem(list.uid);
		store.applyFeed(makeFeed({ seq: 8, full: true, lists: [list], items: [item] }));

		expect(store.lists).toEqual([list]);
		expect(store.itemsOf(list.uid)).toEqual([item]);
		expect(store.seq).toBe(8);
		expect(store.room).toEqual(ROOM);
	});

	it('upserts by uid and removes deletions on a delta', () => {
		const store = storeWith();
		const list = makeList();
		const milk = makeItem(list.uid, { name: 'milk' });
		const eggs = makeItem(list.uid, { name: 'eggs' });
		store.applyFeed(makeFeed({ seq: 2, full: true, lists: [list], items: [milk, eggs] }));

		const milkChanged = { ...milk, quantity: 3, changed_seq: 3 };
		const bread = makeItem(list.uid, { name: 'bread' });
		store.applyFeed(
			makeFeed({
				seq: 4,
				room: { ...ROOM, name: 'Renamed' },
				items: [milkChanged, bread],
				deletions: [{ kind: 'item', uid: eggs.uid }]
			})
		);

		expect(store.itemsOf(list.uid).map((item) => item.name)).toEqual(['bread', 'milk']);
		expect(store.item(milk.uid)?.quantity).toBe(3);
		expect(store.item(eggs.uid)).toBeUndefined();
		expect(store.room?.name).toBe('Renamed');
	});

	it('drops the items of a deleted list, listed in the feed or not', () => {
		const store = storeWith();
		const list = makeList();
		const other = makeList({ name: 'Other' });
		const items = [makeItem(list.uid), makeItem(list.uid, { name: 'eggs' })];
		const kept = makeItem(other.uid);
		store.applyFeed(
			makeFeed({ seq: 2, full: true, lists: [list, other], items: [...items, kept] })
		);

		store.applyFeed(makeFeed({ seq: 3, deletions: [{ kind: 'list', uid: list.uid }] }));

		expect(store.lists).toEqual([other]);
		expect(store.itemsOf(list.uid)).toEqual([]);
		expect(store.server.items.size).toBe(1);
		expect(store.item(kept.uid)).toEqual(kept);
	});

	it('ignores a delta older than its seq', () => {
		const store = storeWith();
		const list = makeList();
		store.applyFeed(makeFeed({ seq: 10, full: true, lists: [list] }));

		const stale = makeFeed({ seq: 9, deletions: [{ kind: 'list', uid: list.uid }] });
		expect(store.applyFeed(stale)).toBe(false);
		expect(store.lists).toEqual([list]);
		expect(store.seq).toBe(10);
	});

	it('applies a full feed with a lower seq (database restore)', () => {
		const store = storeWith();
		store.applyFeed(makeFeed({ seq: 10, full: true, lists: [makeList()] }));
		const list = makeList({ name: 'Restored' });

		expect(store.applyFeed(makeFeed({ seq: 4, full: true, lists: [list] }))).toBe(true);
		expect(store.lists).toEqual([list]);
		expect(store.seq).toBe(4);
	});

	it('sorts lists by name ignoring case and finds them by slug', () => {
		const store = storeWith();
		const b = makeList({ name: 'beta', slug: 'beta-1' });
		const a = makeList({ name: 'Alpha', slug: 'alpha-1' });
		store.applyFeed(makeFeed({ seq: 1, full: true, lists: [b, a] }));

		expect(store.lists.map((list) => list.name)).toEqual(['Alpha', 'beta']);
		expect(store.listBySlug('beta-1')).toEqual(b);
	});

	it('computes visible items with the list setting', () => {
		const store = storeWith();
		const list = makeList({ hide_done: { mode: 'all', age_days: 7, recent_count: 10 } });
		const open = makeItem(list.uid, { name: 'open' });
		const done = makeItem(list.uid, { name: 'done', done: true });
		store.applyFeed(makeFeed({ seq: 1, full: true, lists: [list], items: [open, done] }));

		expect(store.itemsOf(list.uid)).toEqual([open, done]);
		expect(store.visibleItemsOf(list.uid)).toEqual([open]);
	});
});

describe('RoomStore.refresh', () => {
	it('loads with since=seq and becomes ready', async () => {
		const changes = vi.fn(async () => makeFeed({ seq: 3, full: true }));
		const store = storeWith(changes);
		expect(store.status).toBe('loading');

		await store.refresh();
		await store.refresh();

		expect(changes.mock.calls).toEqual([
			[ROOM.slug, 0],
			[ROOM.slug, 3]
		]);
		expect(store.status).toBe('ready');
	});

	it('runs at most one request and queues at most one more', async () => {
		const answers = [deferred<Feed>(), deferred<Feed>()];
		let calls = 0;
		const changes = vi.fn(async (_slug: string, since: number) => {
			void since;
			calls += 1;
			return answers[calls - 1].promise;
		});
		const store = storeWith(changes);

		const first = store.refresh();
		const second = store.refresh();
		const third = store.refresh();
		expect(second).toBe(third);
		expect(changes).toHaveBeenCalledTimes(1);

		answers[0].resolve(makeFeed({ seq: 2, full: true }));
		await first;
		await settle();
		expect(changes).toHaveBeenCalledTimes(2);
		expect(changes.mock.calls[1][1]).toBe(2);

		answers[1].resolve(makeFeed({ seq: 5 }));
		await third;
		expect(store.seq).toBe(5);
		expect(changes).toHaveBeenCalledTimes(2);
	});

	it('asks for sign-in on 401', async () => {
		const store = storeWith(async () => {
			throw new ApiError(401, 'not_authenticated', 'Sign in to this room.');
		});
		await store.refresh();
		expect(store.status).toBe('auth_required');
	});

	it('shows an error on a failed first load, but keeps data later', async () => {
		let fail = true;
		const store = storeWith(async () => {
			if (fail) throw new NetworkError();
			return makeFeed({ seq: 1, full: true, lists: [makeList()] });
		});
		await store.refresh();
		expect(store.status).toBe('error');

		fail = false;
		await store.refresh();
		expect(store.status).toBe('ready');
		expect(store.error).toBeNull();

		fail = true;
		await store.refresh();
		expect(store.status).toBe('ready');
		expect(store.error).toBe('No connection to the server.');
		expect(store.lists).toHaveLength(1);
	});

	it('catchUp joins a running refresh', async () => {
		const answer = deferred<Feed>();
		const changes = vi.fn(() => answer.promise);
		const store = storeWith(changes);

		void store.refresh();
		const caughtUp = store.catchUp(4);
		answer.resolve(makeFeed({ seq: 4, full: true }));
		await caughtUp;

		expect(changes).toHaveBeenCalledTimes(1);
		expect(store.seq).toBe(4);
	});
});

describe('optimistic overlay', () => {
	function loaded() {
		const store = storeWith();
		const list = makeList({ tags: ['Lidl'] });
		const item = makeItem(list.uid, { quantity: 2, tags: ['Lidl'] });
		store.applyFeed(makeFeed({ seq: 5, full: true, lists: [list], items: [item] }));
		return { store, list, item };
	}

	it('shows a pending op at once, keeps server state apart, and settles after the feed', () => {
		const { store, list, item } = loaded();
		const op = sent({ type: 'item.set_done', list_uid: list.uid, item_uid: item.uid, done: true });

		store.opQueued(op);
		expect(store.item(item.uid)?.done).toBe(true);
		expect(store.item(item.uid)?.completed_at).not.toBeNull();
		expect(store.server.items.get(item.uid)?.done).toBe(false);

		store.opSettled(op, { op_id: op.op_id, status: 'applied', result: {}, seq: 6 });
		// Still projected: the feed with seq 6 has not arrived yet.
		expect(store.item(item.uid)?.done).toBe(true);
		expect(store.pendingOps).toHaveLength(1);

		const serverItem = { ...item, done: true, completed_at: '2026-10-03T09:00:00.000000Z' };
		store.applyFeed(makeFeed({ seq: 6, items: [serverItem] }));
		expect(store.pendingOps).toHaveLength(0);
		expect(store.item(item.uid)).toEqual(serverItem);
	});

	it('drops an applied op at once if the feed is already there', () => {
		const { store, list, item } = loaded();
		const op = sent({
			type: 'item.quantity_delta',
			list_uid: list.uid,
			item_uid: item.uid,
			delta: 1
		});
		store.opQueued(op);
		store.applyFeed(makeFeed({ seq: 7, items: [{ ...item, quantity: 3 }] }));
		expect(store.item(item.uid)?.quantity).toBe(4); // still pending: counted twice for now

		store.opSettled(op, { op_id: op.op_id, status: 'applied', result: {}, seq: 6 });
		expect(store.item(item.uid)?.quantity).toBe(3);
	});

	it('reverts a rejected op and shows its message', () => {
		const { store, list, item } = loaded();
		const op = sent({ type: 'item.delete', list_uid: list.uid, item_uid: item.uid });
		store.opQueued(op);
		expect(store.itemsOf(list.uid)).toEqual([]);

		store.opSettled(op, {
			op_id: op.op_id,
			status: 'rejected',
			code: 'list_unavailable',
			message: 'The list is no longer available.',
			seq: 5
		});
		expect(store.itemsOf(list.uid)).toEqual([item]);
		expect(store.notice).toMatchObject({
			code: 'list_unavailable',
			message: 'The list is no longer available.'
		});
	});

	it('reverts a failed op and shows the error', () => {
		const { store, list, item } = loaded();
		const op = sent({ type: 'item.toggle_tag', list_uid: list.uid, item_uid: item.uid, tag: 'X' });
		store.opQueued(op);
		expect(store.item(item.uid)?.tags).toEqual(['Lidl', 'X']);

		store.opFailed(op, new ApiError(422, 'invalid_request', 'This request is not valid.'));
		expect(store.item(item.uid)?.tags).toEqual(['Lidl']);
		expect(store.notice?.code).toBe('invalid_request');
	});

	it('does not project ops that wait for the server', () => {
		const { store, list } = loaded();
		store.opQueued(sent({ type: 'item.add', list_uid: list.uid, name: 'bread' }));
		store.opQueued(sent({ type: 'list.rename', list_uid: list.uid, name: 'X', base_seq: 1 }));
		expect(store.pendingOps).toHaveLength(0);
		expect(store.itemsOf(list.uid)).toHaveLength(1);
	});
});

describe('project', () => {
	const list = makeList({ tags: ['Lidl', 'market'] });
	const item = makeItem(list.uid, {
		quantity: 2,
		done: true,
		completed_at: '2026-01-01T00:00:00Z',
		tags: ['a', 'b']
	});
	const server = { lists: new Map([[list.uid, list]]), items: new Map([[item.uid, item]]) };
	const run = (...ops: Op[]) =>
		project(
			server,
			ops.map((op) => ({ op: sent(op), at: '2026-10-03T12:00:00.000Z', appliedSeq: null }))
		);
	const keys = { list_uid: list.uid, item_uid: item.uid };

	it('returns the server data unchanged without pending ops', () => {
		expect(project(server, [])).toBe(server);
	});

	it('sets done, keeping the time when already done', () => {
		expect(run({ type: 'item.set_done', ...keys, done: true }).items.get(item.uid)).toBe(item);
		const unchecked = run({ type: 'item.set_done', ...keys, done: false }).items.get(item.uid);
		expect(unchecked).toMatchObject({ done: false, completed_at: null });
		const rechecked = run(
			{ type: 'item.set_done', ...keys, done: false },
			{ type: 'item.set_done', ...keys, done: true }
		).items.get(item.uid);
		expect(rechecked).toMatchObject({ done: true, completed_at: '2026-10-03T12:00:00.000Z' });
	});

	it('changes the quantity, never below 1', () => {
		expect(
			run({ type: 'item.quantity_delta', ...keys, delta: 3 }).items.get(item.uid)?.quantity
		).toBe(5);
		expect(
			run({ type: 'item.quantity_delta', ...keys, delta: -5 }).items.get(item.uid)?.quantity
		).toBe(1);
	});

	it('toggles item tags, appending new ones', () => {
		expect(run({ type: 'item.toggle_tag', ...keys, tag: 'a' }).items.get(item.uid)?.tags).toEqual([
			'b'
		]);
		expect(run({ type: 'item.toggle_tag', ...keys, tag: 'C' }).items.get(item.uid)?.tags).toEqual([
			'a',
			'b',
			'C'
		]);
	});

	it('hides a deleted item and ignores ops on missing or moved items', () => {
		expect(run({ type: 'item.delete', ...keys }).items.has(item.uid)).toBe(false);
		const moved = { ...keys, list_uid: 'other' };
		expect(run({ type: 'item.delete', ...moved }).items.get(item.uid)).toBe(item);
		expect(
			run({ type: 'item.set_done', list_uid: list.uid, item_uid: 'gone', done: true }).items.size
		).toBe(1);
	});

	it('adds list tags trimmed and sorted, and removes exact matches', () => {
		const added = run({ type: 'list.tag_add', list_uid: list.uid, tag: '  Coop ' });
		expect(added.lists.get(list.uid)?.tags).toEqual(['Coop', 'Lidl', 'market']);
		expect(run({ type: 'list.tag_add', list_uid: list.uid, tag: '  ' }).lists.get(list.uid)).toBe(
			list
		);
		const removed = run(
			{ type: 'list.tag_remove', list_uid: list.uid, tag: 'lidl' },
			{ type: 'list.tag_remove', list_uid: list.uid, tag: 'market' }
		);
		expect(removed.lists.get(list.uid)?.tags).toEqual(['Lidl']);
	});

	it('merges only the sent hide-done fields', () => {
		const changed = run({
			type: 'list.visibility',
			list_uid: list.uid,
			mode: 'recent',
			recent_count: 3
		});
		expect(changed.lists.get(list.uid)?.hide_done).toEqual({
			mode: 'recent',
			age_days: 7,
			recent_count: 3
		});
		expect(list.hide_done.mode).toBe('off');
	});
});
