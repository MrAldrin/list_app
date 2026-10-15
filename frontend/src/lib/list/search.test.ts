import { describe, expect, it } from 'vitest';
import { searchItems } from './search';

const item = (name: string, description = '', tags: string[] = []) => ({
	name,
	description,
	tags
});

const items = [
	item('milk', 'Oat or cow'),
	item('bread', '', ['Bakery']),
	item('oat milk', 'For coffee')
];

describe('searchItems', () => {
	it('returns every item for an empty or blank text', () => {
		expect(searchItems(items, '')).toEqual(items);
		expect(searchItems(items, '   ')).toEqual(items);
	});

	it('returns a new array, so the caller may change it', () => {
		const found = searchItems(items, '');
		expect(found).not.toBe(items);
	});

	it('matches names, descriptions and tags, ignoring case', () => {
		expect(searchItems(items, 'MIL').map((found) => found.name)).toEqual(['milk', 'oat milk']);
		expect(searchItems(items, 'cow').map((found) => found.name)).toEqual(['milk']);
		expect(searchItems(items, 'bakery').map((found) => found.name)).toEqual(['bread']);
	});

	it('ignores outer spaces in the text', () => {
		expect(searchItems(items, '  bread ').map((found) => found.name)).toEqual(['bread']);
	});

	it('keeps the order of the items', () => {
		expect(searchItems(items, 'o').map((found) => found.name)).toEqual(['milk', 'oat milk']);
	});

	it('finds nothing when no item matches', () => {
		expect(searchItems(items, 'eggs')).toEqual([]);
		expect(searchItems([], 'milk')).toEqual([]);
	});
});
