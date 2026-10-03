// Tag rules of the list page, as NiceGUI's list page has them (`src/main.py`):
// tag chips filter the items, letter buttons on each row toggle a tag.

import type { Item } from '#lib/data/index.ts';

/** How many tag colors there are (`--tag-0` … `--tag-6` in app.css, NiceGUI's `TAG_COLORS`). */
export const TAG_COLOR_COUNT = 7;

/** The CSS color of the tag at `index` in the list's sorted tags. */
export function tagColor(index: number): string {
	return `var(--tag-${index % TAG_COLOR_COUNT})`;
}

/** The letter on an item's tag button: the first letter, upper case. */
export function tagLetter(tag: string): string {
	const first = Array.from(tag)[0];
	return first ? first.toUpperCase() : '?';
}

/**
 * The filter in use: the chosen tag while the list still has it. A tag that
 * someone deleted (here or on another device) stops filtering.
 */
export function activeFilter(chosen: string | null, listTags: readonly string[]): string | null {
	return chosen !== null && listTags.includes(chosen) ? chosen : null;
}

/** Filters by one tag (exact match). Run it after hiding checked items. */
export function filterByTag<T extends Pick<Item, 'tags'>>(
	items: readonly T[],
	tag: string | null
): T[] {
	return tag === null ? [...items] : items.filter((item) => item.tags.includes(tag));
}

/**
 * The tag to add from the "Add Tag" field, or null to do nothing: blank, or
 * already on the list (exact match, as NiceGUI).
 */
export function newTag(raw: string, listTags: readonly string[]): string | null {
	const tag = raw.trim();
	return tag && !listTags.includes(tag) ? tag : null;
}
