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

// Color themes (palettes): which colors light and dark mode use. Saved per
// browser next to the mode, under its own key.

/** One ready-made color theme. `id` is its `data-palette` value in `app.css`. */
export type Palette = {
	id: string;
	name: string;
	/** Where the colors come from, and under which license. */
	source: string;
	license: string;
};

/**
 * The menu's color themes, in menu order. The first is the default. Step 2
 * (a custom theme) adds an entry here and its own colors.
 */
export const PALETTES: readonly Palette[] = [
	{ id: 'classic', name: 'Classic', source: 'This app', license: 'Project' },
	{ id: 'nord', name: 'Nord', source: 'https://www.nordtheme.com', license: 'MIT' },
	{
		id: 'solarized',
		name: 'Solarized',
		source: 'https://ethanschoonover.com/solarized',
		license: 'MIT'
	},
	{ id: 'gruvbox', name: 'Gruvbox', source: 'https://github.com/morhetz/gruvbox', license: 'MIT' },
	{
		id: 'catppuccin',
		name: 'Catppuccin',
		source: 'https://catppuccin.com/palette',
		license: 'MIT'
	},
	{ id: 'rosepine', name: 'Rosé Pine', source: 'https://rosepinetheme.com/palette', license: 'MIT' }
];

export const DEFAULT_PALETTE = PALETTES[0].id;

export const PALETTE_KEY = 'listapp_palette';

/** The saved color theme, or the default when nothing (or something unknown) is saved. */
export function savedPalette(storage = browserStorage()): string {
	try {
		const value = storage?.getItem(PALETTE_KEY);
		return PALETTES.some((palette) => palette.id === value) ? (value as string) : DEFAULT_PALETTE;
	} catch {
		return DEFAULT_PALETTE;
	}
}

/** Saves the color theme; false when this browser cannot. */
export function savePalette(id: string, storage = browserStorage()): boolean {
	try {
		if (!storage) return false;
		storage.setItem(PALETTE_KEY, id);
		return true;
	} catch {
		return false;
	}
}
