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
	/** Background, surface, text, primary, and three tag colors. */
	swatches: Record<Theme, readonly string[]>;
};

/**
 * The menu's color themes, in menu order. The first is the default. Step 2
 * (a custom theme) adds an entry here and its own colors.
 */
export const PALETTES: readonly Palette[] = [
	{
		id: 'classic',
		swatches: {
			light: ['#f4f5f7', '#ffffff', '#1f2933', '#2563eb', '#1565c0', '#2e7d32', '#d32f2f'],
			dark: ['#111418', '#1c2128', '#e6e9ee', '#5b8def', '#64b5f6', '#81c784', '#e57373']
		},
		name: 'Classic',
		source: 'This app',
		license: 'Project'
	},
	{
		id: 'nord',
		swatches: {
			light: ['#eceff4', '#ffffff', '#2e3440', '#506e92', '#506e92', '#607053', '#a4535b'],
			dark: ['#2e3440', '#3b4252', '#eceff4', '#88c0d0', '#98b2cc', '#a3be8c', '#d9a0a6']
		},
		name: 'Nord',
		source: 'https://www.nordtheme.com',
		license: 'MIT'
	},
	{
		id: 'solarized',
		swatches: {
			light: ['#fdf6e3', '#eee8d5', '#073642', '#1e6ca4', '#1e6ca4', '#606e00', '#c42d2a'],
			dark: ['#002b36', '#073642', '#eee8d5', '#4da0da', '#4da0da', '#90a217', '#e87876']
		},
		name: 'Solarized',
		source: 'https://ethanschoonover.com/solarized',
		license: 'MIT'
	},
	{
		id: 'gruvbox',
		swatches: {
			light: ['#fbf1c7', '#f9f5d7', '#3c3836', '#076678', '#076678', '#746f0d', '#9d0006'],
			dark: ['#282828', '#3c3836', '#ebdbb2', '#89aa9d', '#89aa9d', '#b8bb26', '#fc7c6d']
		},
		name: 'Gruvbox',
		source: 'https://github.com/morhetz/gruvbox',
		license: 'MIT'
	},
	{
		id: 'catppuccin',
		swatches: {
			light: ['#eff1f5', '#ffffff', '#4c4f69', '#1d63ee', '#1d63ee', '#317b21', '#d20f39'],
			dark: ['#1e1e2e', '#313244', '#cdd6f4', '#89b4fa', '#89b4fa', '#a6e3a1', '#f38ba8']
		},
		name: 'Catppuccin',
		source: 'https://catppuccin.com/palette',
		license: 'MIT'
	},
	{
		id: 'rosepine',
		swatches: {
			light: ['#faf4ed', '#fffaf3', '#575279', '#286983', '#286983', '#45767f', '#a2596e'],
			dark: ['#191724', '#1f1d2e', '#e0def4', '#c4a7e7', '#588ea4', '#9ccfd8', '#eb6f92']
		},
		name: 'Rosé Pine',
		source: 'https://rosepinetheme.com/palette',
		license: 'MIT'
	}
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
