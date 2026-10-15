// The list page's search: the typed text filters the items by name,
// description and tags. Outer spaces and letter case do not count.

import type { Item } from '#lib/data/index.ts';

/**
 * The items that contain the text in their name, description or a tag, in
 * their order. The text is trimmed and compared without case. Blank text
 * finds every item.
 */
export function searchItems<T extends Pick<Item, 'name' | 'description' | 'tags'>>(
	items: readonly T[],
	text: string
): T[] {
	const query = text.trim().toLowerCase();
	if (!query) return [...items];
	return items.filter((item) =>
		[item.name, item.description, ...item.tags].some((value) => value.toLowerCase().includes(query))
	);
}
