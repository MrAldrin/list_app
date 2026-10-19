// Tag rules of the list page, as NiceGUI's list page has them (`src/main.py`):
// tag chips filter the items, letter buttons on each row toggle a tag.

import type { Item } from '#lib/data/index.ts';

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

/** The CSS color of a tag, from its name. Two tags may share a color; their letters then differ. */
export function tagColor(tag: string): string {
	return `var(--tag-${tagHash(tag) % TAG_COLOR_COUNT})`;
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
