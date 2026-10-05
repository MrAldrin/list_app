// @vitest-environment happy-dom
// The theme store against a fake browser: `data-theme`, the theme-color tag,
// the saved choice and following the system's mode.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { startTheme, theme, toggleTheme } from './theme.svelte';

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
});

const themeColor = () =>
	document.querySelector('meta[name="theme-color"]')?.getAttribute('content');

describe('startTheme', () => {
	it('follows the system while nothing is saved', () => {
		const system = fakeSystem(true);
		stop = startTheme();
		expect(theme.current).toBe('dark');
		expect(document.documentElement.dataset.theme).toBe('dark');

		system.set(false);
		expect(theme.current).toBe('light');
		expect(document.documentElement.dataset.theme).toBe('light');
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
		vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
			throw new Error('full');
		});
		expect(toggleTheme()).toBe(false);
		expect(theme.current).toBe('dark');
		vi.restoreAllMocks();
	});
});
