// Tag rules of the list page, as NiceGUI's list page has them (`src/main.py`):
// tag chips filter the items, letter buttons on each row toggle a tag. The
// tag settings are the list's and live on the server (`list.tag_settings`);
// these rules are pure.

import type { Item, TagSettings } from '#lib/data/index.ts';

/** How many tag colors there are (`--tag-0` … `--tag-6` in app.css, NiceGUI's `TAG_COLORS`). */
export const TAG_COLOR_COUNT = 7;

/** The most letters a tag button shows. */
export const MAX_TAG_LETTERS = 3;

/**
 * A number from the tag's name (FNV-1a, 32 bit). It depends on the name only,
 * so a tag keeps its color when other tags are added or deleted.
 */
export function tagHash(tag: string): number {
	let hash = 0x811c9dc5;
	for (let index = 0; index < tag.length; index += 1) {
		hash ^= tag.charCodeAt(index);
		hash = Math.imul(hash, 0x01000193);
	}
	return hash >>> 0;
}

/** The palette index (0 to 6) a tag gets from its name, when no color was chosen. */
export function defaultTagColor(tag: string): number {
	return tagHash(tag) % TAG_COLOR_COUNT;
}

/** The CSS color of palette entry `index`. */
export function colorVar(index: number): string {
	return `var(--tag-${index})`;
}

/** The palette index of a tag: its chosen color, else the default from its name. */
export function tagColorIndex(settings: Pick<TagSettings, 'colors'>, tag: string): number {
	return Object.hasOwn(settings.colors, tag) ? settings.colors[tag] : defaultTagColor(tag);
}

/** The CSS color of a tag. Two tags may share a color; their letters then differ. */
export function tagColor(settings: Pick<TagSettings, 'colors'>, tag: string): string {
	return colorVar(tagColorIndex(settings, tag));
}

/** The first `length` characters of the tag, trimmed, with the first one in upper case. */
function tagPrefix(tag: string, length: number): string {
	const [first = '?', ...rest] = Array.from(tag.trim()).slice(0, length);
	return (first.toUpperCase() + rest.join('')).trimEnd();
}

/**
 * The letters on the tag buttons of an item, one per tag, in the same order.
 * Each tag shows its first letter. Where two tags show the same letters, both
 * grow by one letter, up to `MAX_TAG_LETTERS`: "Dairy" and "Dry goods" show
 * "Da" and "Dr". Tags that stay the same (for example "Dairy" and "Dairy
 * products") keep the longest letters.
 */
export function tagLetters(tags: readonly string[]): string[] {
	const lengths = tags.map(() => 1);
	for (;;) {
		const letters = tags.map((tag, index) => tagPrefix(tag, lengths[index]));
		const clashing = tags.map((_, index) =>
			letters.some((other, otherIndex) => otherIndex !== index && other === letters[index])
		);
		let grew = false;
		tags.forEach((tag, index) => {
			const longest = Math.min(MAX_TAG_LETTERS, Array.from(tag.trim()).length);
			if (clashing[index] && lengths[index] < longest) {
				lengths[index] += 1;
				grew = true;
			}
		});
		if (!grew) return letters;
	}
}

/**
 * The filters in use: the chosen tags the list still has, in the list's order.
 * A tag that someone deleted (here or on another device) stops filtering.
 */
export function activeFilters(chosen: readonly string[], listTags: readonly string[]): string[] {
	return listTags.filter((tag) => chosen.includes(tag));
}

/**
 * Filters by tags (exact match): keeps the items that have every tag. No tags
 * keeps all. Run it after hiding checked items.
 */
export function filterByTags<T extends Pick<Item, 'tags'>>(
	items: readonly T[],
	tags: readonly string[]
): T[] {
	return items.filter((item) => tags.every((tag) => item.tags.includes(tag)));
}

/**
 * The tag to add from the "Add Tag" field, or null to do nothing: blank, or
 * already on the list (exact match, as NiceGUI).
 */
export function newTag(raw: string, listTags: readonly string[]): string | null {
	const tag = raw.trim();
	return tag && !listTags.includes(tag) ? tag : null;
}

/**
 * The tags an item keeps when it switches to one tag per item: its first tag
 * in the list's order. Tags the list no longer has come after the others.
 * Mirrors `_keep_first_item_tag_locked` in the API.
 */
export function extraTagsOf(itemTags: readonly string[], listTags: readonly string[]): string[] {
	const rank = (tag: string) => {
		const index = listTags.indexOf(tag);
		return index < 0 ? Infinity : index;
	};
	const [, ...extra] = [...itemTags].sort((a, b) => rank(a) - rank(b));
	return extra;
}

/** How many items have several tags: the switch to "One tag per item" must ask first. */
export function countSeveralTags(items: readonly Pick<Item, 'tags'>[]): number {
	return items.filter((item) => item.tags.length > 1).length;
}

/** The question on the confirm dialog before switching to one tag per item. */
export function severalTagsQuestion(count: number): string {
	return count === 1
		? '1 item has several tags. Keep only the first tag on it?'
		: `${count} items have several tags. Keep only the first tag on each?`;
}
