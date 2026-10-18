import { describe, expect, it } from 'vitest';
import { isProjected, project, projectRoom, type PendingOp } from './overlay';
import { NEW_ROW_SEQ } from './rebase';
import { makeItem, makeList, ROOM } from './test-helpers';
import type { Item, List, Op, Room, SentOp } from './types';

const AT = '2026-10-06T18:00:00.000Z';
let counter = 0;

function pending(op: Op, extra: Partial<PendingOp> = {}): PendingOp {
	counter += 1;
	return { op: { ...op, op_id: `op-${counter}` } as SentOp, at: AT, appliedSeq: null, ...extra };
}

function server(lists: List[], items: Item[]) {
	return {
		lists: new Map(lists.map((list) => [list.uid, list])),
		items: new Map(items.map((item) => [item.uid, item]))
	};
}

const list = makeList({ uid: 'list-1', name: 'Groceries', tags: ['Lidl'] });
const milk = makeItem(list.uid, { uid: 'item-milk', name: 'milk', changed_seq: 4 });
const bread = makeItem(list.uid, {
	uid: 'item-bread',
	name: 'bread',
	done: true,
	completed_at: AT
});

function view(...ops: PendingOp[]) {
	return project(server([list], [milk, bread]), ops);
}

describe('overlay: which ops are projected', () => {
	it.each<Op>([
		{ type: 'room.rename', name: 'x' },
		{ type: 'list.create', name: 'x' },
		{ type: 'list.rename', list_uid: 'l', name: 'x', base_seq: 1 },
		{ type: 'list.delete', list_uid: 'l' },
		{ type: 'list.tag_add', list_uid: 'l', tag: 'x' },
		{ type: 'list.tag_remove', list_uid: 'l', tag: 'x' },
		{ type: 'list.visibility', list_uid: 'l', mode: 'all' },
		{ type: 'item.add', list_uid: 'l', name: 'x', uid: 'u' },
		{ type: 'item.set_done', list_uid: 'l', item_uid: 'i', done: true },
		{ type: 'item.quantity_delta', list_uid: 'l', item_uid: 'i', delta: 1 },
		{ type: 'item.edit', list_uid: 'l', item_uid: 'i', name: 'x', description: '', base_seq: 1 },
		{ type: 'item.toggle_tag', list_uid: 'l', item_uid: 'i', tag: 'x', active: true },
		{ type: 'item.delete', list_uid: 'l', item_uid: 'i' },
		{
			type: 'item.restore',
			list_uid: 'l',
			uid: 'u',
			name: 'x',
			done: false,
			tags: [],
			description: '',
			quantity: 1,
			completed_at: null
		}
	])('%o is projected except list.create', (op) => {
		const sent = { ...op, op_id: 'x' } as SentOp;
		expect(isProjected(sent)).toBe(op.type !== 'list.create');
	});
});

describe('overlay: item ops', () => {
	it('adds a new row with the client uid, normalized name and placeholder seq', () => {
		const data = view(
			pending({ type: 'item.add', list_uid: list.uid, name: '  Eggs ', uid: 'new-1' })
		);
		expect(data.items.get('new-1')).toEqual({
			uid: 'new-1',
			list_uid: list.uid,
			name: 'eggs',
			done: false,
			completed_at: null,
			quantity: 1,
			description: '',
			date: null,
			tags: [],
			add_count: 1,
			added_at: AT,
			changed_seq: NEW_ROW_SEQ
		});
	});

	it('adds nothing when an active item with the name exists', () => {
		const data = view(
			pending({ type: 'item.add', list_uid: list.uid, name: 'MILK', uid: 'new-1' })
		);
		expect([...data.items.keys()].sort()).toEqual(['item-bread', 'item-milk']);
	});

	it('unchecks a checked item with the name instead of adding a row', () => {
		const data = view(
			pending({ type: 'item.add', list_uid: list.uid, name: 'Bread', uid: 'new-1' })
		);
		expect([...data.items.keys()].sort()).toEqual(['item-bread', 'item-milk']);
		expect(data.items.get('item-bread')).toMatchObject({ done: false, completed_at: null });
	});

	it('edits name, description and quantity; an absent quantity keeps it', () => {
		const data = view(
			pending({
				type: 'item.edit',
				list_uid: list.uid,
				item_uid: milk.uid,
				name: ' Whole MILK ',
				description: ' cold ',
				base_seq: 4
			})
		);
		expect(data.items.get(milk.uid)).toMatchObject({
			name: 'whole milk',
			description: 'cold',
			quantity: 1
		});
		const withQuantity = view(
			pending({
				type: 'item.edit',
				list_uid: list.uid,
				item_uid: milk.uid,
				name: 'milk',
				description: '',
				quantity: 0,
				base_seq: 4
			})
		);
		expect(withQuantity.items.get(milk.uid)?.quantity).toBe(1);
	});

	it('restores a deleted item unless its name is taken', () => {
		const restore = (name: string) =>
			pending({
				type: 'item.restore',
				list_uid: list.uid,
				uid: 'back-1',
				name,
				done: true,
				tags: ['Lidl'],
				description: ' note ',
				quantity: 3,
				completed_at: '2026-10-05T10:00:00.000Z'
			});
		const data = view(restore('eggs'));
		expect(data.items.get('back-1')).toMatchObject({
			name: 'eggs',
			done: true,
			completed_at: '2026-10-05T10:00:00.000Z',
			tags: ['Lidl'],
			description: 'note',
			quantity: 3
		});
		const taken = view(restore('milk'));
		expect(taken.items.has('back-1')).toBe(false);
	});

	it('keeps completed_at only for a done restore', () => {
		const data = view(
			pending({
				type: 'item.restore',
				list_uid: list.uid,
				uid: 'back-1',
				name: 'eggs',
				done: false,
				tags: [],
				description: '',
				quantity: 1,
				completed_at: '2026-10-05T10:00:00.000Z'
			})
		);
		expect(data.items.get('back-1')?.completed_at).toBeNull();
	});

	it('keeps the server changed_seq of a projected item', () => {
		const data = view(
			pending({
				type: 'item.set_done',
				list_uid: list.uid,
				item_uid: milk.uid,
				done: true,
				base_seq: 4
			})
		);
		expect(data.items.get(milk.uid)).toMatchObject({ done: true, changed_seq: 4 });
	});

	it('ignores edits on rows that are not there', () => {
		const data = view(
			pending({
				type: 'item.edit',
				list_uid: list.uid,
				item_uid: 'gone',
				name: 'x',
				description: '',
				base_seq: 1
			})
		);
		expect(data.items.has('gone')).toBe(false);
	});

	it('sets a tag to the wanted state, and toggles only without one', () => {
		const on = view(
			pending({
				type: 'item.toggle_tag',
				list_uid: list.uid,
				item_uid: milk.uid,
				tag: 'Market',
				active: true
			})
		);
		expect(on.items.get(milk.uid)?.tags).toEqual(['Market']);
		const off = view(
			pending({
				type: 'item.toggle_tag',
				list_uid: list.uid,
				item_uid: milk.uid,
				tag: 'Market',
				active: false
			})
		);
		expect(off.items.get(milk.uid)?.tags).toEqual([]);
		const flip = view(
			pending({ type: 'item.toggle_tag', list_uid: list.uid, item_uid: milk.uid, tag: 'Lidl' })
		);
		expect(flip.items.get(milk.uid)?.tags).toEqual(['Lidl']);
		const flipOff = view(
			pending({ type: 'item.toggle_tag', list_uid: list.uid, item_uid: milk.uid, tag: 'Lidl' }),
			pending({ type: 'item.toggle_tag', list_uid: list.uid, item_uid: milk.uid, tag: 'Lidl' })
		);
		expect(flipOff.items.get(milk.uid)?.tags).toEqual([]);
	});

	it('still projects a wanted-state tag after it was sent without an answer', () => {
		const data = view(
			pending(
				{
					type: 'item.toggle_tag',
					list_uid: list.uid,
					item_uid: milk.uid,
					tag: 'Market',
					active: true
				},
				{ uncertain: true }
			)
		);
		expect(data.items.get(milk.uid)?.tags).toEqual(['Market']);
	});

	it('skips counting ops (delta, untagged toggle) once they were sent without an answer', () => {
		const data = view(
			pending(
				{ type: 'item.quantity_delta', list_uid: list.uid, item_uid: milk.uid, delta: 2 },
				{ uncertain: true }
			),
			pending(
				{ type: 'item.toggle_tag', list_uid: list.uid, item_uid: milk.uid, tag: 'Lidl' },
				{ uncertain: true }
			)
		);
		expect(data.items.get(milk.uid)).toMatchObject({ quantity: 1, tags: [] });
	});

	it('deletes an item, and a list deletes its items', () => {
		expect(
			view(pending({ type: 'item.delete', list_uid: list.uid, item_uid: milk.uid })).items.has(
				milk.uid
			)
		).toBe(false);
		const data = view(pending({ type: 'list.delete', list_uid: list.uid }));
		expect(data.lists.size).toBe(0);
		expect(data.items.size).toBe(0);
	});
});

describe('overlay: list and room ops', () => {
	it('renames a list', () => {
		const data = view(
			pending({ type: 'list.rename', list_uid: list.uid, name: '  Shop ', base_seq: 1 })
		);
		expect(data.lists.get(list.uid)?.name).toBe('Shop');
	});

	it('projects tags and visibility as before', () => {
		const data = view(
			pending({ type: 'list.tag_add', list_uid: list.uid, tag: 'Market' }),
			pending({ type: 'list.tag_remove', list_uid: list.uid, tag: 'Lidl' }),
			pending({ type: 'list.visibility', list_uid: list.uid, mode: 'all' })
		);
		expect(data.lists.get(list.uid)).toMatchObject({
			tags: ['Market'],
			hide_done: { mode: 'all', age_days: 7, recent_count: 10 }
		});
	});

	it('renames the room, and only with a room in view', () => {
		const room: Room = { ...ROOM };
		const ops = [pending({ type: 'room.rename', name: '  Family ' })];
		expect(projectRoom(room, ops)).toEqual({ ...ROOM, name: 'Family' });
		expect(projectRoom(null, ops)).toBeNull();
		expect(projectRoom(room, [])).toBe(room);
	});
});

describe('overlay: answered rows', () => {
	it('shows an answered row with its new changed_seq until the feed has it', () => {
		const data = project(
			server([list], [milk]),
			[],
			[
				{ row: `item:${milk.uid}`, changed_seq: 9, appliedSeq: 7 },
				{ row: `list:${list.uid}`, changed_seq: 10, appliedSeq: 7 }
			]
		);
		expect(data.items.get(milk.uid)?.changed_seq).toBe(9);
		expect(data.lists.get(list.uid)?.changed_seq).toBe(10);
		expect(milk.changed_seq).toBe(4);
	});
});
