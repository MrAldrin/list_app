import { describe, expect, it } from 'vitest';
import { effectiveTheme, otherTheme, savedTheme, saveTheme, THEME_KEY } from './theme';

/** A tiny in-memory Storage, enough for these helpers. */
function memoryStorage(initial: Record<string, string> = {}): Storage {
	const data = new Map(Object.entries(initial));
	return {
		getItem: (key: string) => data.get(key) ?? null,
		setItem: (key: string, value: string) => void data.set(key, value),
		removeItem: (key: string) => void data.delete(key),
		clear: () => data.clear(),
		key: () => null,
		get length() {
			return data.size;
		}
	};
}

const blocked = {
	getItem: () => {
		throw new Error('blocked');
	},
	setItem: () => {
		throw new Error('blocked');
	}
} as unknown as Storage;

describe('savedTheme', () => {
	it("reads NiceGUI's key", () => {
		expect(THEME_KEY).toBe('listapp_theme');
		expect(savedTheme(memoryStorage({ listapp_theme: 'dark' }))).toBe('dark');
		expect(savedTheme(memoryStorage({ listapp_theme: 'light' }))).toBe('light');
	});

	it('is null when nothing or something unknown is saved, or storage is blocked', () => {
		expect(savedTheme(memoryStorage())).toBeNull();
		expect(savedTheme(memoryStorage({ listapp_theme: 'blue' }))).toBeNull();
		expect(savedTheme(blocked)).toBeNull();
		expect(savedTheme(null)).toBeNull();
	});
});

describe('effectiveTheme', () => {
	it('follows the system without a saved choice', () => {
		expect(effectiveTheme(null, true)).toBe('dark');
		expect(effectiveTheme(null, false)).toBe('light');
	});

	it('lets a saved choice win over the system', () => {
		expect(effectiveTheme('light', true)).toBe('light');
		expect(effectiveTheme('dark', false)).toBe('dark');
	});
});

describe('saveTheme', () => {
	it('saves the choice', () => {
		const storage = memoryStorage();
		expect(saveTheme('dark', storage)).toBe(true);
		expect(storage.getItem(THEME_KEY)).toBe('dark');
	});

	it('reports when the browser cannot save', () => {
		expect(saveTheme('dark', blocked)).toBe(false);
		expect(saveTheme('dark', null)).toBe(false);
	});
});

it('otherTheme switches between the two', () => {
	expect(otherTheme('light')).toBe('dark');
	expect(otherTheme('dark')).toBe('light');
});
