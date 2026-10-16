import { describe, expect, it } from 'vitest';
import { NEW_ROW_SEQ, planRewrites, rowOf } from './rebase';
import type { OpResponse, SentOp } from './types';

let counter = 0;
function sent(op: Record<string, unknown>): SentOp {
	counter += 1;
	return { ...op, op_id: `op-${counter}` } as unknown as SentOp;
}

const applied = (op: SentOp, result: Record<string, unknown>): OpResponse => ({
	op_id: op.op_id,
	status: 'applied',
	result,
	seq: 9
});

const rejected = (op: SentOp, extra: Record<string, unknown> = {}): OpResponse =>
	({
		op_id: op.op_id,
		status: 'rejected',
		code: 'duplicate_active',
		message: 'taken',
		seq: 9,
		...extra
	}) as OpResponse;

const none = () => undefined;

function plan(
	settled: SentOp,
	response: OpResponse,
	later: SentOp[],
	options: { sent?: string[]; known?: Record<string, number> } = {}
) {
	const sentIds = new Set(options.sent ?? []);
	return planRewrites({
		settled,
		response,
		later,
		sent: (opId) => sentIds.has(opId),
		knownSeq: (row) => options.known?.[row] ?? none()
	});
}

const edit = (base_seq: number, itemUid = 'milk', name = 'milk') =>
	sent({ type: 'item.edit', list_uid: 'l', item_uid: itemUid, name, description: '', base_seq });

describe('rowOf', () => {
	it('names the item or list an op changes', () => {
		expect(rowOf(sent({ type: 'item.set_done', list_uid: 'l', item_uid: 'i', done: true }))).toBe(
			'item:i'
		);
		expect(rowOf(sent({ type: 'list.rename', list_uid: 'l', name: 'x', base_seq: 1 }))).toBe(
			'list:l'
		);
		expect(rowOf(sent({ type: 'item.add', list_uid: 'l', name: 'x', uid: 'u' }))).toBeNull();
	});
});

describe('R3: own ops on the same row', () => {
	it('moves a later op with the same base to the new changed_seq', () => {
		const tick = sent({
			type: 'item.set_done',
			list_uid: 'l',
			item_uid: 'milk',
			done: true,
			base_seq: 5
		});
		const later = edit(5);
		const rewrites = plan(tick, applied(tick, { changed_seq: 7 }), [later]);
		expect(rewrites).toEqual([{ opId: later.op_id, op: { ...later, base_seq: 7 } }]);
	});

	it('leaves a later op alone when its base was based on another view', () => {
		const tick = sent({
			type: 'item.set_done',
			list_uid: 'l',
			item_uid: 'milk',
			done: true,
			base_seq: 5
		});
		expect(plan(tick, applied(tick, { changed_seq: 7 }), [edit(3)])).toEqual([]);
	});

	it('leaves ops on other rows alone', () => {
		const tick = sent({
			type: 'item.set_done',
			list_uid: 'l',
			item_uid: 'milk',
			done: true,
			base_seq: 5
		});
		expect(plan(tick, applied(tick, { changed_seq: 7 }), [edit(5, 'bread')])).toEqual([]);
	});

	it('does not rewrite an op that was sent (in flight or retried)', () => {
		const tick = sent({
			type: 'item.set_done',
			list_uid: 'l',
			item_uid: 'milk',
			done: true,
			base_seq: 5
		});
		const later = edit(5);
		expect(plan(tick, applied(tick, { changed_seq: 7 }), [later], { sent: [later.op_id] })).toEqual(
			[]
		);
	});

	it('uses the known row seq when the settled op had no base (a delta)', () => {
		const delta = sent({ type: 'item.quantity_delta', list_uid: 'l', item_uid: 'milk', delta: 1 });
		const tick = sent({
			type: 'item.set_done',
			list_uid: 'l',
			item_uid: 'milk',
			done: true,
			base_seq: 5
		});
		const rewrites = plan(delta, applied(delta, { changed_seq: 8 }), [tick], {
			known: { 'item:milk': 5 }
		});
		expect(rewrites).toEqual([{ opId: tick.op_id, op: { ...tick, base_seq: 8 } }]);
	});

	it('rebases a list rename after a list tag change', () => {
		const tag = sent({ type: 'list.tag_add', list_uid: 'l', tag: 'Market' });
		const rename = sent({ type: 'list.rename', list_uid: 'l', name: 'Shop', base_seq: 2 });
		const rewrites = plan(tag, applied(tag, { changed_seq: 3 }), [rename], {
			known: { 'list:l': 2 }
		});
		expect(rewrites).toEqual([{ opId: rename.op_id, op: { ...rename, base_seq: 3 } }]);
	});

	it('does nothing without a changed_seq in the answer', () => {
		const tick = sent({
			type: 'item.set_done',
			list_uid: 'l',
			item_uid: 'milk',
			done: true,
			base_seq: 5
		});
		expect(plan(tick, applied(tick, {}), [edit(5)])).toEqual([]);
		expect(plan(tick, rejected(tick, { code: 'changed_meanwhile' }), [edit(5)])).toEqual([]);
	});
});

describe('R3 for a row this device created', () => {
	it('moves ops on the new row (placeholder base) to the answered changed_seq', () => {
		const add = sent({ type: 'item.add', list_uid: 'l', name: 'eggs', uid: 'new-1' });
		const tick = sent({
			type: 'item.set_done',
			list_uid: 'l',
			item_uid: 'new-1',
			done: true,
			base_seq: NEW_ROW_SEQ
		});
		const rewrites = plan(
			add,
			applied(add, { item_uid: 'new-1', outcome: 'added', changed_seq: 11 }),
			[tick]
		);
		expect(rewrites).toEqual([{ opId: tick.op_id, op: { ...tick, base_seq: 11 } }]);
	});
});

describe('R6: uid remap after an add', () => {
	it('moves later ops to the uid of a restored item, and their placeholder base to its seq', () => {
		const add = sent({ type: 'item.add', list_uid: 'l', name: 'milk', uid: 'client-1' });
		const qty = sent({
			type: 'item.quantity_delta',
			list_uid: 'l',
			item_uid: 'client-1',
			delta: 1
		});
		const edited = sent({
			type: 'item.edit',
			list_uid: 'l',
			item_uid: 'client-1',
			name: 'milk',
			description: 'x',
			base_seq: NEW_ROW_SEQ
		});
		const rewrites = plan(
			add,
			applied(add, { item_uid: 'kept-1', outcome: 'restored', changed_seq: 12 }),
			[qty, edited]
		);
		expect(rewrites).toEqual([
			{ opId: qty.op_id, op: { ...qty, item_uid: 'kept-1' } },
			{ opId: edited.op_id, op: { ...edited, item_uid: 'kept-1', base_seq: 12 } }
		]);
	});

	it('moves ops to the existing item of a duplicate_active rejection', () => {
		const add = sent({ type: 'item.add', list_uid: 'l', name: 'milk', uid: 'client-1' });
		const tag = sent({
			type: 'item.toggle_tag',
			list_uid: 'l',
			item_uid: 'client-1',
			tag: 'Lidl',
			active: true
		});
		const rewrites = plan(add, rejected(add, { item_uid: 'kept-1' }), [tag]);
		expect(rewrites).toEqual([{ opId: tag.op_id, op: { ...tag, item_uid: 'kept-1' } }]);
	});

	it('keeps the client uid when the server kept it', () => {
		const add = sent({ type: 'item.add', list_uid: 'l', name: 'milk', uid: 'client-1' });
		const tag = sent({
			type: 'item.toggle_tag',
			list_uid: 'l',
			item_uid: 'client-1',
			tag: 'Lidl',
			active: true
		});
		expect(
			plan(add, applied(add, { item_uid: 'client-1', outcome: 'added', changed_seq: 3 }), [tag])
		).toEqual([]);
	});

	it('does not move a sent op', () => {
		const add = sent({ type: 'item.add', list_uid: 'l', name: 'milk', uid: 'client-1' });
		const tag = sent({
			type: 'item.toggle_tag',
			list_uid: 'l',
			item_uid: 'client-1',
			tag: 'Lidl',
			active: true
		});
		expect(plan(add, rejected(add, { item_uid: 'kept-1' }), [tag], { sent: [tag.op_id] })).toEqual(
			[]
		);
	});
});
