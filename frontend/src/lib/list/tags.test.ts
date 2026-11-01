import { describe, expect, it } from 'vitest';
import {
	activeFilters,
	countSeveralTags,
	extraTagsOf,
	filterByTags,
	newTag,
	severalTagsQuestion,
	tagColor,
	tagColorIndex,
	tagHash,
	tagLetters
} from './tags';

const NO_COLORS = { colors: {} };

describe('tagColor', () => {
	it('is one of the seven palette colors', () => {
		for (const tag of ['Lidl', 'Market', '🍎 fruit', 'é', 'x'.repeat(100)]) {
			expect(tagColor(NO_COLORS, tag)).toMatch(/^var\(--tag-[0-6]\)$/);
		}
	});

	it('stays the same for a name, whatever other tags the list has', () => {
		// Pinned values: a change here would recolor every tag on every list.
		expect(tagColor(NO_COLORS, 'Lidl')).toBe('var(--tag-0)');
		expect(tagColor(NO_COLORS, 'Market')).toBe('var(--tag-6)');
		expect(tagColor(NO_COLORS, 'Dairy')).toBe('var(--tag-5)');
		expect(tagHash('Lidl')).toBe(tagHash('Lidl'));
	});

	it('is the same for the same name in any list order', () => {
		const first = tagLetters(['Lidl', 'Market']);
		const second = tagLetters(['Market', 'Lidl']);
		expect(first).toEqual(['L', 'M']);
		expect(second).toEqual(['M', 'L']);
		expect(tagColor(NO_COLORS, 'Market')).toBe('var(--tag-6)');
	});

	it('uses the chosen color of the list, and the default for the others', () => {
		const settings = { colors: { Lidl: 4 } };
		expect(tagColor(settings, 'Lidl')).toBe('var(--tag-4)');
		expect(tagColorIndex(settings, 'Market')).toBe(6);
	});
});

describe('tagLetters', () => {
	it('is the first letter in upper case, one per tag', () => {
		expect(tagLetters(['lidl', 'Market', 'éclair'])).toEqual(['L', 'M', 'É']);
	});

	it('keeps a whole emoji and falls back to "?"', () => {
		expect(tagLetters(['🍎 fruit'])).toEqual(['🍎']);
		expect(tagLetters([''])).toEqual(['?']);
	});

	it('shows two letters when two tags share the first letter', () => {
		expect(tagLetters(['Dairy', 'Dry goods'])).toEqual(['Da', 'Dr']);
	});

	it('shows only the tags that clash with each other longer', () => {
		expect(tagLetters(['Dairy', 'Dry goods', 'Lidl'])).toEqual(['Da', 'Dr', 'L']);
	});

	it('grows a tag until it is different from the others', () => {
		expect(tagLetters(['Dairy', 'Dairy products', 'Dry'])).toEqual(['Dai', 'Dai', 'Dr']);
		expect(tagLetters(['D', 'Dairy'])).toEqual(['D', 'Da']);
	});

	it('stops at three letters when names stay alike', () => {
		expect(tagLetters(['Dairy', 'Dairy products'])).toEqual(['Dai', 'Dai']);
	});

	it('tells apart a space-separated name, and does not end a letter with a space', () => {
		expect(tagLetters(['🍎 fruit', '🍎 juice'])).toEqual(['🍎 f', '🍎 j']);
		expect(tagLetters(['Ab cd', 'Ab ef'])).toEqual(['Ab', 'Ab']);
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

describe('single-mode tag rules', () => {
	it('keeps the first tag in the list order and drops the others', () => {
		// The list order is aldi, Lidl, Market (ignoring case).
		const listTags = ['aldi', 'Lidl', 'Market'];
		expect(extraTagsOf(['Market', 'Lidl', 'aldi'], listTags)).toEqual(['Lidl', 'Market']);
		expect(extraTagsOf(['Lidl', 'Market'], listTags)).toEqual(['Market']);
	});

	it('puts tags the list no longer has after the others', () => {
		expect(extraTagsOf(['gone', 'Market'], ['Market'])).toEqual(['gone']);
	});

	it('keeps nothing extra for one tag or none', () => {
		expect(extraTagsOf(['Lidl'], ['Lidl'])).toEqual([]);
		expect(extraTagsOf([], ['Lidl'])).toEqual([]);
	});

	it('counts the items with several tags and asks in the right words', () => {
		const items = [{ tags: ['a'] }, { tags: ['a', 'b'] }, { tags: ['a', 'b', 'c'] }];
		expect(countSeveralTags(items)).toBe(2);
		expect(severalTagsQuestion(1)).toBe('1 item has several tags. Keep only the first tag on it?');
		expect(severalTagsQuestion(2)).toBe(
			'2 items have several tags. Keep only the first tag on each?'
		);
	});
});
