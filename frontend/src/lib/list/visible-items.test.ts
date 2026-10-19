import { describe, expect, it } from 'vitest';
import { makeItem } from '#lib/data/test-helpers.ts';
import type { Item } from '#lib/data/index.ts';
import { itemSortChoice } from '#lib/data/order.ts';
import { visibleItems, type VisibleItemsInput } from './visible-items.ts';

const name = itemSortChoice('name-asc')!;

function items(...specs: Partial<Item>[]): Item[] {
	return specs.map((spec, index) => makeItem('list-1', { uid: `u${index}`, ...spec }));
}

function input(overrides: Partial<VisibleItemsInput> = {}): VisibleItemsInput {
	const all = overrides.all ?? [];
	return {
		all,
		notHidden: () => all,
		searchText: '',
		filtersBySearch: false,
		tags: [],
		sort: name,
		hold: null,
		...overrides
	};
}

const names = (rows: Item[]) => rows.map((row) => row.name);

describe('visibleItems', () => {
	it('sorts open items first, then by name', () => {
		const all = items(
			{ name: 'eggs', done: true, completed_at: '2026-10-01T00:00:00Z' },
			{ name: 'milk' },
			{ name: 'bread' }
		);
		expect(names(visibleItems(input({ all })))).toEqual(['bread', 'milk', 'eggs']);
	});

	it('uses the hide-done rule when no search applies', () => {
		const all = items({ name: 'milk' }, { name: 'eggs', done: true });
		const rows = visibleItems(input({ all, notHidden: () => [all[0]] }));
		expect(names(rows)).toEqual(['milk']);
	});

	it('does not call the hide-done rule while a search applies', () => {
		const all = items({ name: 'milk' }, { name: 'oat milk' }, { name: 'eggs' });
		let called = false;
		const rows = visibleItems(
			input({
				all,
				searchText: ' MILK ',
				filtersBySearch: true,
				notHidden: () => {
					called = true;
					return [];
				}
			})
		);
		expect(called).toBe(false);
		expect(names(rows)).toEqual(['milk', 'oat milk']);
	});

	it('only suggests while online: typed text does not filter an online list', () => {
		const all = items({ name: 'milk' }, { name: 'eggs' });
		const rows = visibleItems(input({ all, searchText: 'mil', filtersBySearch: false }));
		expect(names(rows)).toEqual(['eggs', 'milk']);
	});

	it('treats blank search text as no search', () => {
		const all = items({ name: 'milk' }, { name: 'eggs', done: true });
		const rows = visibleItems(
			input({ all, searchText: '   ', filtersBySearch: true, notHidden: () => [all[0]] })
		);
		expect(names(rows)).toEqual(['milk']);
	});

	it('keeps only the items with every chosen tag', () => {
		const all = items(
			{ name: 'milk', tags: ['dairy', 'cold'] },
			{ name: 'bread', tags: ['dairy'] },
			{ name: 'rice', tags: ['dry'] }
		);
		expect(names(visibleItems(input({ all, tags: ['dairy'] })))).toEqual(['bread', 'milk']);
		expect(names(visibleItems(input({ all, tags: ['dairy', 'cold'] })))).toEqual(['milk']);
	});

	it('applies the chosen sort after the filters', () => {
		const all = items({ name: 'bread' }, { name: 'milk' });
		const rows = visibleItems(input({ all, sort: itemSortChoice('name-desc')! }));
		expect(names(rows)).toEqual(['milk', 'bread']);
	});

	it('keeps held rows in the place they had on screen', () => {
		const all = items({ name: 'apple' }, { name: 'bread' }, { name: 'cake' });
		const [apple, bread, cake] = all;
		const rows = visibleItems(
			input({
				all,
				hold: { shown: [cake.uid, apple.uid, bread.uid], uids: new Set([cake.uid]) }
			})
		);
		expect(rows.map((row) => row.uid)).toEqual([cake.uid, apple.uid, bread.uid]);
	});

	it('returns an empty list for an empty list', () => {
		expect(visibleItems(input())).toEqual([]);
	});
});
