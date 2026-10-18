import { describe, expect, it } from 'vitest';
import {
	addedLabel,
	addFeedback,
	checkFeedback,
	formatItemDate,
	itemSuggestions,
	lastAddedLabel,
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

describe('checkFeedback', () => {
	it('names the item, neutral for both', () => {
		expect(checkFeedback('milk', true)).toEqual({ message: 'Checked milk', kind: 'info' });
		expect(checkFeedback('milk', false)).toEqual({ message: 'Unchecked milk', kind: 'info' });
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

describe('formatItemDate', () => {
	it('shows the day and month, as written', () => {
		expect(formatItemDate('2026-10-18')).toBe('18 Oct');
		expect(formatItemDate('2026-01-05')).toBe('5 Jan');
		// The day must not shift with the time zone.
		expect(formatItemDate('2027-03-01')).toBe('1 Mar');
	});
});

describe('addedLabel', () => {
	it('says once for 1 and the count otherwise', () => {
		expect(addedLabel(1)).toBe('Added once');
		expect(addedLabel(2)).toBe('Added 2 times');
		expect(addedLabel(5)).toBe('Added 5 times');
	});
});

describe('lastAddedLabel', () => {
	// The expected text is built from local time, so the test passes in any time zone.
	it('shows the local date and 24-hour time of the last add', () => {
		const at = new Date(2026, 9, 18, 14, 8, 30);
		expect(lastAddedLabel(at.toISOString())).toBe('Last added 2026-10-18 14:08');
	});

	it('pads single-digit months, days, hours and minutes', () => {
		const at = new Date(2026, 0, 5, 9, 4, 0);
		expect(lastAddedLabel(at.toISOString())).toBe('Last added 2026-01-05 09:04');
	});

	it('shows midnight as 00:00', () => {
		const at = new Date(2026, 9, 18, 0, 0, 0);
		expect(lastAddedLabel(at.toISOString())).toBe('Last added 2026-10-18 00:00');
	});

	it('shows nothing for an item with no time, or a time that is not one', () => {
		expect(lastAddedLabel(null)).toBeNull();
		expect(lastAddedLabel('yesterday')).toBeNull();
	});
});
