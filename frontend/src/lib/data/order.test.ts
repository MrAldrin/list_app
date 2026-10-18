import { describe, expect, it } from 'vitest';
import { makeItem } from './test-helpers';
import { ITEM_SORTS, itemSortChoice, sortItems, type ItemSort } from './order';
import type { Item } from './types';

const names = (items: Item[]) => items.map((item) => item.name);
const sorted = (items: Item[], sort: ItemSort) => names(sortItems(items, sort));

const OLD = '2026-01-01T10:00:00.000Z';
const NEW = '2026-10-18T09:00:00.000Z';

describe('name sort', () => {
	const items = [
		makeItem('l', { name: 'b' }),
		makeItem('l', { name: 'c', done: true }),
		makeItem('l', { name: 'Apple' }),
		makeItem('l', { name: 'a', done: true })
	];

	it('is name A–Z, open items first, ignoring case', () => {
		expect(sorted(items, { key: 'name', reverse: false })).toEqual(['Apple', 'b', 'a', 'c']);
	});

	it('reverses to Z–A, still open items first', () => {
		expect(sorted(items, { key: 'name', reverse: true })).toEqual(['b', 'Apple', 'c', 'a']);
	});
});

describe('date sort', () => {
	const items = [
		makeItem('l', { name: 'none-b', date: null }),
		makeItem('l', { name: 'late', date: '2026-12-01' }),
		makeItem('l', { name: 'none-a', date: null }),
		makeItem('l', { name: 'soon', date: '2026-10-18' }),
		makeItem('l', { name: 'overdue', date: '2026-01-05' }),
		makeItem('l', { name: 'done-soon', date: '2026-10-19', done: true })
	];

	it('soonest first: dated items by date, then undated by name', () => {
		expect(sorted(items, { key: 'date', reverse: false })).toEqual([
			'overdue',
			'soon',
			'late',
			'none-a',
			'none-b',
			'done-soon'
		]);
	});

	it('latest first: dated items come first too, undated still last by name', () => {
		expect(sorted(items, { key: 'date', reverse: true })).toEqual([
			'late',
			'soon',
			'overdue',
			'none-a',
			'none-b',
			'done-soon'
		]);
	});
});

describe('added sort', () => {
	const items = [
		makeItem('l', { name: 'old', added_at: OLD }),
		makeItem('l', { name: 'no-time', added_at: null }),
		makeItem('l', { name: 'new', added_at: NEW }),
		makeItem('l', { name: 'done-new', added_at: NEW, done: true })
	];

	it('newest first: no time is last', () => {
		expect(sorted(items, { key: 'added', reverse: false })).toEqual([
			'new',
			'old',
			'no-time',
			'done-new'
		]);
	});

	it('oldest first: no time counts as oldest, so it is first', () => {
		expect(sorted(items, { key: 'added', reverse: true })).toEqual([
			'no-time',
			'old',
			'new',
			'done-new'
		]);
	});
});

describe('most added sort', () => {
	const items = [
		makeItem('l', { name: 'once', add_count: 1 }),
		makeItem('l', { name: 'many', add_count: 7 }),
		makeItem('l', { name: 'twice', add_count: 2 }),
		makeItem('l', { name: 'many-done', add_count: 9, done: true })
	];

	it('most first, checked items below', () => {
		expect(sorted(items, { key: 'most-added', reverse: false })).toEqual([
			'many',
			'twice',
			'once',
			'many-done'
		]);
	});

	it('fewest first', () => {
		expect(sorted(items, { key: 'most-added', reverse: true })).toEqual([
			'once',
			'twice',
			'many',
			'many-done'
		]);
	});
});

describe('ties', () => {
	it('break ties by name A–Z in every direction', () => {
		const items = [
			makeItem('l', { name: 'Cola', add_count: 3, added_at: NEW, date: '2026-10-18' }),
			makeItem('l', { name: 'bread', add_count: 3, added_at: NEW, date: '2026-10-18' }),
			makeItem('l', { name: 'apple', add_count: 3, added_at: NEW, date: '2026-10-18' })
		];
		for (const key of ['date', 'added', 'most-added'] as const) {
			for (const reverse of [false, true]) {
				expect(sorted(items, { key, reverse })).toEqual(['apple', 'bread', 'Cola']);
			}
		}
	});

	it('break ties on undated items by name A–Z too, even going backwards', () => {
		const items = [
			makeItem('l', { name: 'zebra', date: null }),
			makeItem('l', { name: 'ant', date: null })
		];
		expect(sorted(items, { key: 'date', reverse: true })).toEqual(['ant', 'zebra']);
	});
});

describe('ITEM_SORTS', () => {
	it('has unique ids, and the first choice is name A–Z', () => {
		const ids = ITEM_SORTS.map((choice) => choice.id);
		expect(new Set(ids).size).toBe(ids.length);
		expect(ITEM_SORTS[0]).toMatchObject({ id: 'name-asc', label: 'Name A–Z' });
	});

	it('finds a choice by id, and nothing for an unknown id', () => {
		expect(itemSortChoice('added-asc')).toMatchObject({ key: 'added', reverse: true });
		expect(itemSortChoice('bogus')).toBeNull();
		expect(itemSortChoice(null)).toBeNull();
		expect(itemSortChoice(undefined)).toBeNull();
	});

	it('sorts by each choice in the table without throwing', () => {
		const items = [makeItem('l', { name: 'a' }), makeItem('l', { name: 'b', done: true })];
		for (const choice of ITEM_SORTS) {
			expect(sortItems(items, choice)).toHaveLength(2);
		}
	});
});
