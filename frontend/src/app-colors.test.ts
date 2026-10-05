// The color pairs in app.css meet the WCAG contrast minimums in light and
// dark mode: 4.5:1 for text, 3:1 for field edges and focus rings. The test
// reads the CSS file itself, so a new color cannot slip below them.

import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

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

const light = colors(':root');
const dark = { ...light, ...colors(":root[data-theme='dark']") };
const TAGS = ['tag-0', 'tag-1', 'tag-2', 'tag-3', 'tag-4', 'tag-5', 'tag-6'];

describe.each([
	['light', light],
	['dark', dark]
])('%s mode', (_, theme) => {
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
