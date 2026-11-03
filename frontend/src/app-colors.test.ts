// The color pairs in app.css meet the WCAG contrast minimums in light and
// dark mode, for every color theme in PALETTES: 4.5:1 for text, 3:1 for field edges and focus rings. The test
// reads the CSS file itself, so a new color cannot slip below them.

import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { PALETTES } from './lib/ui/theme';

const css = readFileSync(new URL('./app.css', import.meta.url), 'utf8');

/** The `--name: #rrggbb` values of the first block that starts with `selector {`. */
function colors(selector: string): Record<string, string> {
	const start = css.indexOf(`${selector} {`);
	const block = css.slice(start, css.indexOf('\n}', start));
	return Object.fromEntries(
		[...block.matchAll(/--([\w-]+):\s*(#[0-9a-f]{6});/gi)].map((match) => [match[1], match[2]])
	);
}

function luminance(hex: string): number {
	const [r, g, b] = [1, 3, 5].map((at) => {
		const channel = parseInt(hex.slice(at, at + 2), 16) / 255;
		return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
	});
	return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
	const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (light + 0.05) / (dark + 0.05);
}

const classicLight = colors(':root');
const classicDark = { ...classicLight, ...colors(":root[data-theme='dark']") };
const NAMES = Object.keys(classicLight);

/** A palette's own colors; each block must set every color, so none is borrowed. */
function palette(selector: string): Record<string, string> {
	const own = colors(selector);
	expect(Object.keys(own).sort()).toEqual([...NAMES].sort());
	return own;
}

const modes: [string, () => Record<string, string>][] = PALETTES.flatMap(({ id }) =>
	id === 'classic'
		? [
				['classic light', () => classicLight],
				['classic dark', () => classicDark]
			]
		: [
				[`${id} light`, () => palette(`:root[data-palette='${id}']`)],
				[`${id} dark`, () => palette(`:root[data-palette='${id}'][data-theme='dark']`)]
			]
);
const TAGS = ['tag-0', 'tag-1', 'tag-2', 'tag-3', 'tag-4', 'tag-5', 'tag-6'];

describe.each(modes)('%s', (_, read) => {
	const theme = read();
	type Pair = [foreground: string, background: string];
	const pairs = (foreground: string[], background: string[]): Pair[] =>
		foreground.flatMap((fg) => background.map((bg): Pair => [fg, bg]));

	it.each([
		...pairs(['text', 'text-muted', 'primary', 'danger', 'warning', 'success'], ['bg', 'surface']),
		...pairs(TAGS, ['bg', 'surface']),
		['primary-text', 'primary'] as Pair,
		['danger-text', 'danger'] as Pair,
		...pairs(['tag-text'], TAGS)
	])('text %s on %s is at least 4.5:1', (fg, bg) => {
		expect(contrast(theme[fg], theme[bg])).toBeGreaterThanOrEqual(4.5);
	});

	it.each(pairs(['control-border', 'focus'], ['bg', 'surface']))(
		'%s on %s is at least 3:1',
		(fg, bg) => {
			expect(contrast(theme[fg], theme[bg])).toBeGreaterThanOrEqual(3);
		}
	);
});

describe('palette swatches', () => {
	it.each(PALETTES)('$name matches the CSS in both modes', (entry) => {
		for (const mode of ['light', 'dark'] as const) {
			const selector =
				entry.id === 'classic'
					? mode === 'light'
						? ':root'
						: ":root[data-theme='dark']"
					: `:root[data-palette='${entry.id}']${mode === 'dark' ? "[data-theme='dark']" : ''}`;
			const actual = colors(selector);
			expect(entry.swatches[mode]).toEqual(
				['bg', 'surface', 'text', 'primary', 'tag-0', 'tag-1', 'tag-2'].map((key) => actual[key])
			);
		}
	});
});
