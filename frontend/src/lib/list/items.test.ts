import { describe, expect, it } from 'vitest';
import {
	addFeedback,
	itemSuggestions,
	normalizeItemName,
	loadShowQuantities,
	quantityBadge,
	saveShowQuantities,
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

describe('quantityBadge', () => {
	it('shows ×N from 2 when the stepper is off', () => {
		expect(quantityBadge(1, false)).toBeNull();
		expect(quantityBadge(2, false)).toBe('×2');
	});

	it('is not needed when the stepper shows the number', () => {
		expect(quantityBadge(3, true)).toBeNull();
	});
});

describe('show quantities setting', () => {
	function memoryStorage(): Storage {
		const data = new Map<string, string>();
		return {
			get length() {
				return data.size;
			},
			clear: () => data.clear(),
			key: (index) => [...data.keys()][index] ?? null,
			getItem: (key) => data.get(key) ?? null,
			setItem: (key, value) => void data.set(key, value),
			removeItem: (key) => void data.delete(key)
		};
	}

	it('is off until saved, and saved per list', () => {
		const storage = memoryStorage();
		expect(loadShowQuantities('a', storage)).toBe(false);
		saveShowQuantities('a', true, storage);
		expect(loadShowQuantities('a', storage)).toBe(true);
		expect(loadShowQuantities('b', storage)).toBe(false);
		saveShowQuantities('a', false, storage);
		expect(loadShowQuantities('a', storage)).toBe(false);
	});

	it('works without storage', () => {
		const blocked = memoryStorage();
		blocked.getItem = () => {
			throw new Error('blocked');
		};
		blocked.setItem = blocked.getItem;
		expect(loadShowQuantities('a', blocked)).toBe(false);
		expect(() => saveShowQuantities('a', true, blocked)).not.toThrow();
		expect(loadShowQuantities('a', null)).toBe(false);
	});
});

describe('stepQuantity', () => {
	it('adds the step and never goes below 1', () => {
		expect(stepQuantity(2, 1)).toBe(3);
		expect(stepQuantity(2, -1)).toBe(1);
		expect(stepQuantity(1, -1)).toBe(1);
	});
});
