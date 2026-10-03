import { describe, expect, it } from 'vitest';
import {
	addFeedback,
	itemSuggestions,
	normalizeItemName,
	showsQuantity,
	stepQuantity
} from './items';

const named = (...names: string[]) => names.map((name) => ({ name }));

describe('normalizeItemName', () => {
	it('trims and lowercases, like the server', () => {
		expect(normalizeItemName('  Oat Milk ')).toBe('oat milk');
		expect(normalizeItemName('   ')).toBe('');
	});
});

describe('itemSuggestions', () => {
	it('suggests nothing for empty text', () => {
		expect(itemSuggestions(named('milk'), '  ')).toEqual([]);
	});

	it('finds names that contain the text, ignoring case and outer spaces', () => {
		expect(itemSuggestions(named('milk', 'bread', 'oat milk'), ' MIL ')).toEqual([
			'milk',
			'oat milk'
		]);
	});

	it('sorts by code point and keeps at most three', () => {
		const items = named('e', 'ea', 'de', 'ce', 'be', 'ae');
		expect(itemSuggestions(items, 'e')).toEqual(['ae', 'be', 'ce']);
	});

	it('lists a name once', () => {
		expect(itemSuggestions(named('milk', 'milk'), 'milk')).toEqual(['milk']);
	});
});

describe('addFeedback', () => {
	it('uses the NiceGUI texts', () => {
		expect(addFeedback('added', 'milk')).toEqual({ message: 'Added milk', kind: 'success' });
		expect(addFeedback('restored', 'milk')).toEqual({ message: 'Restored milk!', kind: 'info' });
	});
});

describe('showsQuantity', () => {
	it('hides the stepper unless "Show quantities" is on', () => {
		expect(showsQuantity(3, { showQuantities: false, onlyAboveOne: false })).toBe(false);
		expect(showsQuantity(1, { showQuantities: true, onlyAboveOne: false })).toBe(true);
	});

	it('with "Only show minimum 2", shows it only from 2', () => {
		const view = { showQuantities: true, onlyAboveOne: true };
		expect(showsQuantity(1, view)).toBe(false);
		expect(showsQuantity(2, view)).toBe(true);
	});
});

describe('stepQuantity', () => {
	it('adds the step and never goes below 1', () => {
		expect(stepQuantity(2, 1)).toBe(3);
		expect(stepQuantity(2, -1)).toBe(1);
		expect(stepQuantity(1, -1)).toBe(1);
	});
});
