import { describe, expect, it } from 'vitest';
import { activeFilter, filterByTag, newTag, tagColor, tagLetter } from './tags';

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

describe('activeFilter', () => {
	it('keeps a chosen tag the list still has', () => {
		expect(activeFilter('Lidl', ['Lidl', 'Market'])).toBe('Lidl');
		expect(activeFilter(null, ['Lidl'])).toBeNull();
	});

	it('drops a tag that was deleted, also case-sensitively', () => {
		expect(activeFilter('Lidl', ['Market'])).toBeNull();
		expect(activeFilter('lidl', ['Lidl'])).toBeNull();
	});
});

describe('filterByTag', () => {
	const items = [
		{ name: 'milk', tags: ['Lidl'] },
		{ name: 'bread', tags: [] },
		{ name: 'eggs', tags: ['Market', 'Lidl'] }
	];

	it('shows everything without a filter', () => {
		expect(filterByTag(items, null)).toEqual(items);
	});

	it('keeps items with the tag, in order', () => {
		expect(filterByTag(items, 'Lidl').map((item) => item.name)).toEqual(['milk', 'eggs']);
		expect(filterByTag(items, 'lidl')).toEqual([]);
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
