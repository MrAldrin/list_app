import { describe, expect, it } from 'vitest';
import { project, type PendingOp } from './overlay';
import { isSentOp } from './queue-entries';
import { validateData } from './snapshot-validate';
import { makeItem, makeList, ROOM } from './test-helpers';
import type { Item, List, SentOp } from './types';

const AT = '2026-10-18T09:00:00.000Z';
const OLD = '2000-01-01T00:00:00.000Z';

function server(lists: List[], items: Item[]) {
	return {
		lists: new Map(lists.map((list) => [list.uid, list])),
		items: new Map(items.map((item) => [item.uid, item]))
	};
}

function pending(op: Record<string, unknown>): PendingOp {
	return { op: { op_id: 'op', ...op } as SentOp, at: AT, appliedSeq: null };
}

const list = makeList({ uid: 'list-a' });
const milk = makeItem(list.uid, { uid: 'item-milk', name: 'milk', add_count: 2, added_at: OLD });
const bread = makeItem(list.uid, {
	uid: 'item-bread',
	name: 'bread',
	done: true,
	completed_at: OLD,
	add_count: 3,
	added_at: OLD
});

function view(...ops: PendingOp[]) {
	return project(server([list], [milk, bread]), ops);
}

function setDone(uid: string, done: boolean): PendingOp {
	return pending({ type: 'item.set_done', list_uid: list.uid, item_uid: uid, done });
}

describe('add count in pending ops', () => {
	it('an uncheck counts as an add', () => {
		const item = view(setDone(bread.uid, false)).items.get(bread.uid);
		expect(item).toMatchObject({ done: false, add_count: 4, added_at: AT });
	});

	it('a check and an uncheck of an unchecked item do not count', () => {
		expect(view(setDone(milk.uid, true)).items.get(milk.uid)).toMatchObject({
			done: true,
			add_count: 2,
			added_at: OLD
		});
		expect(view(setDone(milk.uid, false)).items.get(milk.uid)).toMatchObject({
			add_count: 2,
			added_at: OLD
		});
	});

	it('an uncheck sent twice counts once', () => {
		// The server already unchecked it, so the page's feed says not done.
		const unchecked = { ...bread, done: false, completed_at: null };
		const data = project(server([list], [unchecked]), [setDone(bread.uid, false)]);
		expect(data.items.get(bread.uid)).toMatchObject({ add_count: 3, added_at: OLD });
	});

	it('re-adding a checked item counts; adding a new one starts at 1', () => {
		const restored = view(
			pending({ type: 'item.add', list_uid: list.uid, name: 'Bread', uid: 'new-1' })
		);
		expect(restored.items.get(bread.uid)).toMatchObject({ add_count: 4, added_at: AT });
		const fresh = view(
			pending({ type: 'item.add', list_uid: list.uid, name: 'Eggs', uid: 'new-1' })
		);
		expect(fresh.items.get('new-1')).toMatchObject({ add_count: 1, added_at: AT });
	});

	it('an undo keeps the count it was sent with, or counts 1 with no time', () => {
		const restore = (extra: Record<string, unknown>) =>
			pending({
				type: 'item.restore',
				list_uid: list.uid,
				uid: 'back-1',
				name: 'eggs',
				done: false,
				tags: [],
				description: '',
				quantity: 1,
				completed_at: null,
				...extra
			});
		expect(view(restore({ add_count: 5, added_at: OLD })).items.get('back-1')).toMatchObject({
			add_count: 5,
			added_at: OLD
		});
		expect(view(restore({})).items.get('back-1')).toMatchObject({
			add_count: 1,
			added_at: null
		});
	});

	it('the write queue keeps the undo fields', () => {
		const op = {
			op_id: 'a',
			type: 'item.restore',
			list_uid: list.uid,
			name: 'eggs',
			done: false,
			tags: [],
			description: '',
			quantity: 1,
			completed_at: null,
			add_count: 5,
			added_at: OLD
		};
		expect(isSentOp(op)).toBe(true);
		expect(isSentOp({ ...op, add_count: 'five' })).toBe(false);
		expect(isSentOp({ ...op, added_at: 7 })).toBe(false);
	});
});

describe('add count in snapshots', () => {
	const identity = { kind: 'room' as const, slug: ROOM.slug };
	const data = (item: Partial<Item> & Record<string, unknown>) => ({
		seq: 5,
		room: ROOM,
		lists: [list],
		items: [{ ...makeItem(list.uid, { changed_seq: 5 }), ...item }]
	});

	it('keeps a counted item', () => {
		const result = validateData(identity, data({ add_count: 3, added_at: OLD }));
		expect(result?.items[0]).toMatchObject({ add_count: 3, added_at: OLD });
	});

	it('reads a snapshot saved before items were counted as 1 with no time', () => {
		const old = makeItem(list.uid, { changed_seq: 5 }) as Partial<Item>;
		delete old.add_count;
		delete old.added_at;
		const result = validateData(identity, { ...data({}), items: [old] });
		expect(result?.items[0]).toMatchObject({ add_count: 1, added_at: null });
	});

	it('rejects a count below 1 or a time that is not a time', () => {
		expect(validateData(identity, data({ add_count: 0 }))).toBeNull();
		expect(validateData(identity, data({ add_count: 1.5 }))).toBeNull();
		expect(validateData(identity, data({ added_at: 'yesterday' }))).toBeNull();
	});
});
