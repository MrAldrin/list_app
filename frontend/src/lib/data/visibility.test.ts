// The cases of tests/test_item_visibility.py, so the client and server agree.
import { describe, expect, it } from 'vitest';
import { sortItems, sortLists, sortTags } from './order';
import { makeItem, makeList } from './test-helpers';
import type { HideDone, HideDoneMode } from './types';
import {
	filterVisibleItems,
	MAX_HIDE_DONE_COUNT,
	parseCompletionTime,
	validateVisibilitySettings
} from './visibility';

function item(id: number, done: boolean, completedAt: string | null = null) {
	// The Python tests use integer ids; here the id doubles as the uid.
	return { uid: String(id).padStart(3, '0'), done, completed_at: completedAt };
}

function settings(mode: HideDoneMode, ageDays = 7, recentCount = 10): HideDone {
	return { mode, age_days: ageDays, recent_count: recentCount };
}

const ids = (rows: { uid: string }[]) => rows.map((row) => Number(row.uid));

describe('filterVisibleItems (parity with item_visibility.py)', () => {
	const now = new Date(Date.UTC(2025, 0, 8, 12));

	it('keeps unchecked and legacy checked items as specified', () => {
		const items = [item(1, false), item(2, true), item(3, true, '2025-01-07T12:00:00Z')];

		expect(ids(filterVisibleItems(items))).toEqual([1, 2, 3]);
		expect(ids(filterVisibleItems(items, settings('all')))).toEqual([1]);
		expect(ids(filterVisibleItems(items, settings('age', 1), now))).toEqual([1, 2]);
		expect(items[1].completed_at).toBeNull();
	});

	it('rejects zero counts in either numeric mode', () => {
		expect(() => filterVisibleItems([], settings('age', 0))).toThrow('age_days');
		expect(() => filterVisibleItems([], settings('recent', 7, 0))).toThrow('recent_count');
	});

	it('uses the exact full 24-hour boundary in age mode', () => {
		const items = [
			item(1, true, '2025-01-01T12:00:00Z'),
			item(2, true, '2025-01-01T12:00:01Z'),
			item(3, true, '2025-01-01T11:59:59Z'),
			item(4, false)
		];
		expect(ids(filterVisibleItems(items, settings('age', 7), now))).toEqual([2, 4]);
	});

	it('compares microseconds at the age boundary, like Python', () => {
		const items = [
			item(1, true, '2025-01-01T12:00:00.000000Z'),
			item(2, true, '2025-01-01T12:00:00.000001Z')
		];
		expect(ids(filterVisibleItems(items, settings('age', 7), now))).toEqual([2]);
	});

	it('ranks known times first in recent mode, then items without a time', () => {
		const items = [
			item(99, true),
			item(4, true, '2025-01-03T00:00:00Z'),
			item(7, true, '2025-01-02T00:00:00Z'),
			item(8, true, '2025-01-02T00:00:00Z'),
			item(10, true, '2025-01-01T00:00:00Z'),
			item(19, true),
			item(20, true),
			item(21, false)
		];
		const visible = (count: number) =>
			new Set(ids(filterVisibleItems(items, settings('recent', 7, count))));

		// Python breaks the 7/8 tie by creation id; the API has no creation order,
		// so only "one of the two" is the same. Here the tie goes by uid.
		const two = visible(2);
		expect(two.has(4) && two.has(21) && two.size === 3).toBe(true);
		expect(two.has(7) !== two.has(8)).toBe(true);

		// All known times are kept before any item without a time.
		const five = visible(5);
		expect([4, 7, 8, 10, 21].every((id) => five.has(id))).toBe(true);
		expect(five.size).toBe(6);
		expect([99, 19, 20].filter((id) => five.has(id))).toHaveLength(1);

		expect(visible(7)).toEqual(new Set([4, 7, 8, 10, 19, 20, 21, 99]));
	});

	it('keeps the given order', () => {
		const items = [item(3, true, '2025-01-01T00:00:00Z'), item(1, false), item(2, true)];
		expect(ids(filterVisibleItems(items, settings('recent', 7, 5)))).toEqual([3, 1, 2]);
	});

	it('validates the mode and count bounds', () => {
		expect(() => filterVisibleItems([], settings('unknown' as HideDoneMode))).toThrow(
			'Unknown checked-item visibility mode'
		);
		expect(() => filterVisibleItems([], settings('age', -1))).toThrow('age_days');
		expect(() => filterVisibleItems([], settings('recent', 7, 1.5))).toThrow('recent_count');
		expect(() => filterVisibleItems([], settings('recent', 7, MAX_HIDE_DONE_COUNT + 1))).toThrow(
			'recent_count'
		);
	});

	it.each([
		['unknown', 7, 10],
		['off', 0, 10],
		['off', 7, 0],
		['off', -1, 10],
		['off', 7, -1],
		['off', 7, 1.5],
		['age', MAX_HIDE_DONE_COUNT + 1, 10],
		['recent', 7, MAX_HIDE_DONE_COUNT + 1]
	])('rejects invalid settings %s/%s/%s', (mode, ageDays, recentCount) => {
		expect(() => validateVisibilitySettings(mode, ageDays, recentCount)).toThrow();
	});
});

describe('parseCompletionTime', () => {
	it('reads the server format and other ISO forms as UTC', () => {
		const base = Date.UTC(2026, 9, 3, 9, 12, 44) * 1000;
		expect(parseCompletionTime('2026-10-03T09:12:44.123456Z')).toBe(base + 123456);
		expect(parseCompletionTime('2026-10-03T09:12:44Z')).toBe(base);
		// No zone counts as UTC (not local time, as Date.parse would read it).
		expect(parseCompletionTime('2026-10-03T09:12:44')).toBe(base);
		expect(parseCompletionTime('2026-10-03T11:12:44+02:00')).toBe(base);
		expect(parseCompletionTime('2026-10-03T09:12:44.5Z')).toBe(base + 500000);
	});

	it('returns null for unreadable values', () => {
		for (const value of [null, undefined, '', 'yesterday', '2026-13-01T00:00:00Z', 42]) {
			expect(parseCompletionTime(value)).toBeNull();
		}
	});
});

describe('sort orders', () => {
	it('sorts items open first, then by name (SQLite NOCASE)', () => {
		const items = [
			makeItem('l', { name: 'b', done: true }),
			makeItem('l', { name: 'c' }),
			makeItem('l', { name: 'a', done: true }),
			makeItem('l', { name: 'B' }),
			makeItem('l', { name: 'äpple' }),
			makeItem('l', { name: 'z' })
		];
		expect(sortItems(items).map((row) => row.name)).toEqual(['B', 'c', 'z', 'äpple', 'a', 'b']);
	});

	it('sorts lists by name ignoring ASCII case', () => {
		const lists = [
			makeList({ name: 'groceries' }),
			makeList({ name: 'Ärenden' }),
			makeList({ name: 'Books' }),
			makeList({ name: 'apples' })
		];
		expect(sortLists(lists).map((list) => list.name)).toEqual([
			'apples',
			'Books',
			'groceries',
			'Ärenden'
		]);
	});

	it('sorts tags like Python sorted(key=str.lower)', () => {
		expect(sortTags(['market', 'Lidl', 'aldi', 'Zoo'])).toEqual(['aldi', 'Lidl', 'market', 'Zoo']);
	});
});
