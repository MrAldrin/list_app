// @vitest-environment happy-dom
// The theme store against a fake browser: `data-theme`, the theme-color tag,
// the saved choice and following the system's mode.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { choosePalette, startTheme, theme, toggleTheme } from './theme.svelte';

/** A fake `matchMedia` whose dark-mode answer the test can change. */
function fakeSystem(dark: boolean) {
	const listeners = new Set<() => void>();
	const media = {
		matches: dark,
		addEventListener: (_: string, listener: () => void) => listeners.add(listener),
		removeEventListener: (_: string, listener: () => void) => listeners.delete(listener)
	};
	vi.stubGlobal('matchMedia', () => media);
	return {
		set(next: boolean) {
			media.matches = next;
			for (const listener of listeners) listener();
		},
		listeners
	};
}

let stop: () => void = () => {};

beforeEach(() => {
	localStorage.clear();
	document.head.innerHTML = '<meta name="theme-color" content="#000000">';
	// app.css is not loaded here; give each mode its own page background.
	document.head.insertAdjacentHTML(
		'beforeend',
		"<style>:root { --bg: #f4f5f7 } :root[data-theme='dark'] { --bg: #111418 }</style>"
	);
});

afterEach(() => {
	stop();
	vi.unstubAllGlobals();
	delete document.documentElement.dataset.theme;
	delete document.documentElement.dataset.palette;
});

const themeColor = () =>
	document.querySelector('meta[name="theme-color"]')?.getAttribute('content');

describe('startTheme', () => {
	it('follows the system while nothing is saved', () => {
		const system = fakeSystem(true);
		stop = startTheme();
		expect(theme.current).toBe('dark');
		expect(document.documentElement.dataset.theme).toBe('dark');
		expect(themeColor()).toBe('#111418');
		expect(localStorage.getItem('listapp_theme')).toBeNull();

		system.set(false);
		expect(theme.current).toBe('light');
		expect(document.documentElement.dataset.theme).toBe('light');
		expect(themeColor()).toBe('#f4f5f7');
		expect(localStorage.getItem('listapp_theme')).toBeNull();

		system.set(true);
		expect(theme.current).toBe('dark');
		expect(document.documentElement.dataset.theme).toBe('dark');
		expect(themeColor()).toBe('#111418');
		expect(localStorage.getItem('listapp_theme')).toBeNull();
	});

	it('keeps a saved choice when the system changes', () => {
		localStorage.setItem('listapp_theme', 'light');
		const system = fakeSystem(true);
		stop = startTheme();
		expect(theme.current).toBe('light');

		system.set(false);
		system.set(true);
		expect(theme.current).toBe('light');
	});

	it('sets the theme-color tag to the page background', () => {
		fakeSystem(false);
		stop = startTheme();
		expect(themeColor()).toBe('#f4f5f7');
		toggleTheme();
		expect(themeColor()).toBe('#111418');
	});

	it('stops following the system when stopped', () => {
		const system = fakeSystem(false);
		startTheme()();
		expect(system.listeners.size).toBe(0);
	});
});

describe('toggleTheme', () => {
	it('switches, saves the choice and then ignores the system', () => {
		const system = fakeSystem(false);
		stop = startTheme();

		expect(toggleTheme()).toBe(true);
		expect(theme.current).toBe('dark');
		expect(localStorage.getItem('listapp_theme')).toBe('dark');

		system.set(true);
		system.set(false);
		expect(theme.current).toBe('dark');

		expect(toggleTheme()).toBe(true);
		expect(document.documentElement.dataset.theme).toBe('light');
		expect(localStorage.getItem('listapp_theme')).toBe('light');
	});

	it('still switches when the choice cannot be saved', () => {
		fakeSystem(false);
		stop = startTheme();
		// A stub, not a spy: happy-dom's storage keeps a spied method as an item.
		vi.stubGlobal('localStorage', {
			getItem: () => null,
			setItem: () => {
				throw new Error('full');
			}
		});
		expect(toggleTheme()).toBe(false);
		expect(theme.current).toBe('dark');
	});
});

it('keeps theme state local to separate browser worlds', async () => {
	const firstStorage = new Map<string, string>();
	const secondStorage = new Map<string, string>();
	const useStorage = (values: Map<string, string>) =>
		vi.stubGlobal('localStorage', {
			getItem: (key: string) => values.get(key) ?? null,
			setItem: (key: string, value: string) => values.set(key, value)
		});
	const system = fakeSystem(false);
	useStorage(firstStorage);
	vi.resetModules();
	const first = await import('./theme.svelte');
	const stopFirst = first.startTheme();
	try {
		expect(first.theme.current).toBe('light');
		expect(first.toggleTheme()).toBe(true);
		expect(first.theme.current).toBe('dark');
		expect(firstStorage.get('listapp_theme')).toBe('dark');
	} finally {
		stopFirst();
	}
	expect(system.listeners.size).toBe(0);
	useStorage(secondStorage);
	vi.resetModules();
	const second = await import('./theme.svelte');
	stop = second.startTheme();
	expect(second.theme).not.toBe(first.theme);
	expect(second.theme.current).toBe('light');
	expect(document.documentElement.dataset.theme).toBe('light');
	expect(themeColor()).toBe('#f4f5f7');
	expect(localStorage.getItem('listapp_theme')).toBeNull();
	expect(secondStorage.size).toBe(0);
	expect(first.theme.current).toBe('dark');
	expect(firstStorage.get('listapp_theme')).toBe('dark');
});

describe('choosePalette', () => {
	it('sets data-palette, saves it and keeps it on the next start', () => {
		fakeSystem(false);
		stop = startTheme();
		expect(document.documentElement.dataset.palette).toBe('classic');

		expect(choosePalette('nord')).toBe(true);
		expect(theme.palette).toBe('nord');
		expect(document.documentElement.dataset.palette).toBe('nord');
		expect(localStorage.getItem('listapp_palette')).toBe('nord');

		toggleTheme();
		expect(document.documentElement.dataset.palette).toBe('nord');
		stop();
		stop = startTheme();
		expect(theme.palette).toBe('nord');
	});
});
