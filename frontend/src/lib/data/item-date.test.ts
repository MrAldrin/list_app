import { describe, expect, it } from 'vitest';
import { isItemDate } from './item-date';
import { project, type PendingOp } from './overlay';
import { isSentOp } from './queue-entries';
import { validateData } from './snapshot-validate';
import { makeItem, makeList, ROOM } from './test-helpers';
import type { Item, List, SentOp } from './types';

const AT = '2026-10-18T09:00:00.000Z';

function server(lists: List[], items: Item[]) {
	return {
		lists: new Map(lists.map((list) => [list.uid, list])),
		items: new Map(items.map((item) => [item.uid, item]))
	};
}

function pending(op: SentOp): PendingOp {
	return { op, at: AT, appliedSeq: null };
}

describe('isItemDate', () => {
	it('accepts real calendar days written YYYY-MM-DD', () => {
		expect(isItemDate('2026-10-18')).toBe(true);
		expect(isItemDate('2024-02-29')).toBe(true);
		expect(isItemDate('0050-01-01')).toBe(true);
	});

	it.each([
		'',
		'2026-1-5',
		'18/10/2026',
		'2026-10-18T00:00:00Z',
		' 2026-10-18',
		'20261018',
		'2026-02-30',
		'2025-02-29',
		'2026-13-01',
		'0000-01-01',
		'２０２６-10-18'
	])('rejects %j', (value) => {
		expect(isItemDate(value)).toBe(false);
	});

	it('rejects values that are not text', () => {
		expect(isItemDate(20261018)).toBe(false);
		expect(isItemDate(null)).toBe(false);
		expect(isItemDate(undefined)).toBe(false);
	});
});

describe('item date in snapshots', () => {
	const list = makeList({ uid: 'list-a' });
	const identity = { kind: 'room' as const, slug: ROOM.slug };
	const data = (item: Record<string, unknown>) => ({
		seq: 5,
		room: ROOM,
		lists: [list],
		items: [{ ...makeItem(list.uid, { changed_seq: 5 }), ...item }]
	});

	it('keeps a dated item', () => {
		const result = validateData(identity, data({ date: '2026-10-18' }));
		expect(result?.items[0].date).toBe('2026-10-18');
	});

	it('reads a snapshot saved before items had dates as no date', () => {
		const old = makeItem(list.uid, { changed_seq: 5 }) as Partial<Item>;
		delete old.date;
		const result = validateData(identity, { ...data({}), items: [old] });
		expect(result?.items[0].date).toBeNull();
	});

	it('rejects a snapshot with a date that is not a real day', () => {
		expect(validateData(identity, data({ date: '2026-02-30' }))).toBeNull();
	});
});

describe('item date in pending ops', () => {
	const list = makeList({ uid: 'list-a' });
	const milk = makeItem(list.uid, { uid: 'item-milk', date: '2026-10-01' });

	it('sets a date, clears it with null, and keeps it when the op has none', () => {
		const set = project(server([list], [milk]), [
			pending({
				type: 'item.edit',
				op_id: 'a',
				list_uid: list.uid,
				item_uid: milk.uid,
				name: 'milk',
				description: '',
				date: '2026-10-18',
				base_seq: 1
			})
		]);
		expect(set.items.get(milk.uid)?.date).toBe('2026-10-18');

		const cleared = project(server([list], [milk]), [
			pending({
				type: 'item.edit',
				op_id: 'b',
				list_uid: list.uid,
				item_uid: milk.uid,
				name: 'milk',
				description: '',
				date: null,
				base_seq: 1
			})
		]);
		expect(cleared.items.get(milk.uid)?.date).toBeNull();

		const kept = project(server([list], [milk]), [
			pending({
				type: 'item.edit',
				op_id: 'c',
				list_uid: list.uid,
				item_uid: milk.uid,
				name: 'oat milk',
				description: '',
				base_seq: 1
			})
		]);
		expect(kept.items.get(milk.uid)?.date).toBe('2026-10-01');
	});

	it('an undo brings back the kept date', () => {
		const data = project(server([list], []), [
			pending({
				type: 'item.restore',
				op_id: 'd',
				uid: 'item-back',
				list_uid: list.uid,
				name: 'milk',
				done: false,
				tags: [],
				description: '',
				quantity: 1,
				completed_at: null,
				date: '2026-10-01'
			})
		]);
		expect(data.items.get('item-back')?.date).toBe('2026-10-01');
	});
});

describe('item date in the write queue', () => {
	const base = {
		op_id: 'e',
		type: 'item.edit',
		list_uid: 'l',
		item_uid: 'i',
		name: 'milk',
		description: '',
		base_seq: 1
	};

	it('accepts a date, null, or no date field', () => {
		expect(isSentOp({ ...base, date: '2026-10-18' })).toBe(true);
		expect(isSentOp({ ...base, date: null })).toBe(true);
		expect(isSentOp(base)).toBe(true);
	});

	it('rejects a date that is not text', () => {
		expect(isSentOp({ ...base, date: 20261018 })).toBe(false);
	});
});
