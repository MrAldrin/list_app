import { describe, expect, it } from 'vitest';
import { holdRowOrder } from './hold-order';

const rows = (...uids: string[]) => uids.map((uid) => ({ uid }));
const uids = (items: { uid: string }[]) => items.map((item) => item.uid);

describe('holdRowOrder', () => {
	it('is the sorted order when no row is held', () => {
		const sorted = rows('c', 'a', 'b');
		expect(uids(holdRowOrder(sorted, ['a', 'b', 'c'], new Set()))).toEqual(['c', 'a', 'b']);
	});

	it('keeps a held row where it was on screen', () => {
		// "a" was checked, so sorting moves it last; the hold keeps it first.
		const sorted = rows('b', 'c', 'a');
		expect(uids(holdRowOrder(sorted, ['a', 'b', 'c'], new Set(['a'])))).toEqual(['a', 'b', 'c']);
	});

	it('keeps several held rows in their places', () => {
		const sorted = rows('c', 'a', 'b');
		expect(uids(holdRowOrder(sorted, ['a', 'b', 'c'], new Set(['a', 'b'])))).toEqual([
			'a',
			'b',
			'c'
		]);
	});

	it('puts rows that are not held in sorted order around the held ones', () => {
		// "x" is new; "b" and "a" are not held and follow the sorted order.
		const sorted = rows('x', 'b', 'a', 'y');
		const shown = ['a', 'b'];
		expect(uids(holdRowOrder(sorted, shown, new Set(['a'])))).toEqual(['a', 'x', 'b', 'y']);
	});

	it('leaves out a held row that is no longer listed', () => {
		const sorted = rows('a', 'c');
		expect(uids(holdRowOrder(sorted, ['a', 'b', 'c'], new Set(['b'])))).toEqual(['a', 'c']);
	});

	it('moves a held row to the sorted place when its shown place is gone', () => {
		// "c" was third, but only two rows are left, so it takes the free place.
		const sorted = rows('a', 'c');
		expect(uids(holdRowOrder(sorted, ['a', 'b', 'c'], new Set(['c'])))).toEqual(['a', 'c']);
	});

	it('does not change the rows it is given', () => {
		const sorted = rows('b', 'a');
		const shown = ['a', 'b'];
		holdRowOrder(sorted, shown, new Set(['a']));
		expect(uids(sorted)).toEqual(['b', 'a']);
		expect(shown).toEqual(['a', 'b']);
	});
});
