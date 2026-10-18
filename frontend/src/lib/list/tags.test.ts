import { describe, expect, it } from 'vitest';
import { activeFilters, filterByTags, newTag, tagColor, tagLetter } from './tags';

describe('tagColor', () => {
	it('cycles through seven colors by position', () => {
		expect(tagColor(0)).toBe('var(--tag-0)');
		expect(tagColor(6)).toBe('var(--tag-6)');
		expect(tagColor(7)).toBe('var(--tag-0)');
	});
});

describe('tagLetter', () => {
	it('is the first letter in upper case', () => {
		expect(tagLetter('lidl')).toBe('L');
		expect(tagLetter('Market')).toBe('M');
		expect(tagLetter('éclair')).toBe('É');
	});

	it('keeps a whole emoji and falls back to "?"', () => {
		expect(tagLetter('🍎 fruit')).toBe('🍎');
		expect(tagLetter('')).toBe('?');
	});
});

describe('activeFilters', () => {
	it('is empty when nothing is chosen', () => {
		expect(activeFilters([], ['Lidl'])).toEqual([]);
	});

	it('keeps the chosen tags the list still has, in the list order', () => {
		expect(activeFilters(['Market', 'Lidl'], ['Lidl', 'Market'])).toEqual(['Lidl', 'Market']);
		expect(activeFilters(['Lidl'], ['Lidl', 'Market'])).toEqual(['Lidl']);
	});

	it('drops a tag that was deleted, also case-sensitively', () => {
		expect(activeFilters(['Lidl'], ['Market'])).toEqual([]);
		expect(activeFilters(['lidl'], ['Lidl'])).toEqual([]);
		expect(activeFilters(['Lidl', 'Gone'], ['Lidl'])).toEqual(['Lidl']);
	});
});

describe('filterByTags', () => {
	const items = [
		{ name: 'milk', tags: ['Lidl', 'Market'] },
		{ name: 'bread', tags: ['Market'] },
		{ name: 'eggs', tags: ['Lidl'] },
		{ name: 'apples', tags: [] }
	];
	const names = (tags: readonly string[]) => filterByTags(items, tags).map((item) => item.name);

	it('shows everything when no tag is chosen', () => {
		expect(filterByTags(items, [])).toEqual(items);
	});

	it('keeps items with the one chosen tag, in order', () => {
		expect(names(['Lidl'])).toEqual(['milk', 'eggs']);
		expect(names(['lidl'])).toEqual([]);
	});

	it('keeps only items with every chosen tag (intersection)', () => {
		expect(names(['Lidl', 'Market'])).toEqual(['milk']);
		expect(names(['Market', 'Lidl'])).toEqual(['milk']);
	});

	it('is empty when no item has all chosen tags', () => {
		expect(names(['Lidl', 'Bakery'])).toEqual([]);
	});
});

describe('newTag', () => {
	it('trims the text', () => {
		expect(newTag('  Lidl ', [])).toBe('Lidl');
	});

	it('ignores blank text and an existing tag (exact match)', () => {
		expect(newTag('   ', [])).toBeNull();
		expect(newTag('Lidl', ['Lidl'])).toBeNull();
		expect(newTag('lidl', ['Lidl'])).toBe('lidl');
	});
});
