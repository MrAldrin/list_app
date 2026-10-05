// The page's light or dark mode, as NiceGUI's "Toggle dark mode" button.
// `app.html` sets it before the first paint; `startTheme()` (root layout)
// keeps it up to date; `ThemeToggle.svelte` switches it. The rules are in
// `theme.ts`.

import { untrack } from 'svelte';
import { effectiveTheme, otherTheme, savedTheme, saveTheme, type Theme } from './theme';

const DARK_QUERY = '(prefers-color-scheme: dark)';

/**
 * `current`: the mode the page shows. `headerToggles`: toggle buttons in the
 * page's own top bar; the layout shows one above the page only when there is none.
 */
export const theme = $state<{ current: Theme; headerToggles: number }>({
	current: 'light',
	headerToggles: 0
});

function systemMedia(): MediaQueryList | null {
	return globalThis.matchMedia?.(DARK_QUERY) ?? null;
}

/**
 * Shows the mode: `data-theme` on `<html>` picks the colors in `app.css`, and
 * the `theme-color` meta tag (the browser's bar color) gets the page
 * background, so Safari can follow a switch.
 */
function apply(next: Theme): void {
	theme.current = next;
	const root = document.documentElement;
	root.dataset.theme = next;
	const background = getComputedStyle(root).getPropertyValue('--bg').trim();
	const meta = document.querySelector('meta[name="theme-color"]');
	if (meta && background) meta.setAttribute('content', background);
}

/** Applies the mode and follows the system while nothing is saved. Returns a stop function. */
export function startTheme(): () => void {
	const media = systemMedia();
	apply(effectiveTheme(savedTheme(), media?.matches ?? false));
	const follow = () => {
		if (savedTheme() === null) apply(effectiveTheme(null, media?.matches ?? false));
	};
	media?.addEventListener('change', follow);
	return () => media?.removeEventListener('change', follow);
}

/** Switches to the other mode and saves it; false when it could not be saved. */
export function toggleTheme(): boolean {
	const next = otherTheme(theme.current);
	apply(next);
	return saveTheme(next);
}

/** Counts a toggle in a top bar while the calling component lives (call in `$effect`). */
export function registerHeaderToggle(): () => void {
	untrack(() => (theme.headerToggles += 1));
	return () => untrack(() => (theme.headerToggles -= 1));
}
