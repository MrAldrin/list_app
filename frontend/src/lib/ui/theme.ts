// Light or dark mode: the small rules, kept out of Svelte so Vitest can test
// them. The choice is per browser, never shared with the room, as NiceGUI's
// "Toggle dark mode" button.

export type Theme = 'light' | 'dark';

/**
 * The localStorage key NiceGUI uses (`listapp_theme`). Both UIs run on the
 * same site, so a choice made in one is also the other's.
 */
export const THEME_KEY = 'listapp_theme';

/** The browser's localStorage, or null where it is blocked (private mode, tests). */
function browserStorage(): Storage | null {
	try {
		return globalThis.localStorage ?? null;
	} catch {
		return null;
	}
}

/** The saved choice, or null when nothing (or something unknown) is saved. */
export function savedTheme(storage = browserStorage()): Theme | null {
	try {
		const value = storage?.getItem(THEME_KEY);
		return value === 'dark' || value === 'light' ? value : null;
	} catch {
		return null;
	}
}

/** A saved choice wins; without one the page follows the phone or computer. */
export function effectiveTheme(saved: Theme | null, systemDark: boolean): Theme {
	return saved ?? (systemDark ? 'dark' : 'light');
}

/** Saves the choice; false when this browser cannot (storage blocked or full). */
export function saveTheme(theme: Theme, storage = browserStorage()): boolean {
	try {
		if (!storage) return false;
		storage.setItem(THEME_KEY, theme);
		return true;
	} catch {
		return false;
	}
}

/** The other one: what the toggle button switches to. */
export function otherTheme(theme: Theme): Theme {
	return theme === 'dark' ? 'light' : 'dark';
}
