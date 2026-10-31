import { describe, expect, it } from 'vitest';
import { classifyEntry, isSentOp, newStoredEntry } from './queue-entries';
import type { SentOp } from './types';

describe('item.add_if_absent queue entries', () => {
	const op: SentOp = {
		op_id: 'op-group-add',
		type: 'item.add_if_absent',
		list_uid: 'list-one',
		name: 'Milk',
		uid: 'optimistic-item'
	};

	it('validates and classifies the operation for ordered offline replay', () => {
		expect(isSentOp(op)).toBe(true);
		expect(
			classifyEntry(
				newStoredEntry(op, '2026-10-06T18:00:00.000Z'),
				Date.parse('2026-10-06T18:01:00.000Z')
			)
		).toMatchObject({ kind: 'ready', op });
	});

	it('keeps malformed add-if-absent entries unreadable', () => {
		expect(isSentOp({ ...op, list_uid: 3 })).toBe(false);
		expect(isSentOp({ ...op, name: null })).toBe(false);
	});
});
