import { describe, expect, it } from 'vitest';
import { memoryStorage } from '../data/test-helpers';
import {
	DEFAULT_PALETTE,
	effectiveTheme,
	otherTheme,
	PALETTE_KEY,
	PALETTES,
	savedPalette,
	savePalette,
	savedTheme,
	saveTheme,
	THEME_KEY
} from './theme';

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

describe('palettes', () => {
	it('starts with Classic and has unique ids, each with a source and license', () => {
		expect(DEFAULT_PALETTE).toBe('classic');
		const ids = PALETTES.map((palette) => palette.id);
		expect(new Set(ids).size).toBe(ids.length);
		for (const palette of PALETTES) {
			expect(palette.source).not.toBe('');
			expect(palette.license).not.toBe('');
		}
	});

	it('reads a saved palette, and falls back to Classic', () => {
		expect(PALETTE_KEY).toBe('listapp_palette');
		expect(savedPalette(memoryStorage({ listapp_palette: 'nord' }))).toBe('nord');
		expect(savedPalette(memoryStorage({ listapp_palette: 'neon' }))).toBe('classic');
		expect(savedPalette(memoryStorage())).toBe('classic');
		expect(savedPalette(blocked)).toBe('classic');
	});

	it('saves the palette, and reports when it cannot', () => {
		const storage = memoryStorage();
		expect(savePalette('gruvbox', storage)).toBe(true);
		expect(storage.getItem(PALETTE_KEY)).toBe('gruvbox');
		expect(savePalette('gruvbox', blocked)).toBe(false);
	});
});
