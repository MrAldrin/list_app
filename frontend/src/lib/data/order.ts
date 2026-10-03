// Sort orders, matching the NiceGUI app and the server.

import type { Item, List } from './types';

/** Compares by Unicode code point, like Python and SQLite (JS `<` compares UTF-16 units). */
export function compareCodePoints(a: string, b: string): number {
	const left = Array.from(a);
	const right = Array.from(b);
	const length = Math.min(left.length, right.length);
	for (let index = 0; index < length; index += 1) {
		const difference = left[index].codePointAt(0)! - right[index].codePointAt(0)!;
		if (difference !== 0) return difference;
	}
	return left.length - right.length;
}

/** SQLite's `COLLATE NOCASE`: folds only A–Z, then compares code points. */
export function compareNoCase(a: string, b: string): number {
	const fold = (text: string) => text.replace(/[A-Z]/g, (letter) => letter.toLowerCase());
	return compareCodePoints(fold(a), fold(b));
}

/** Python's `sorted(tags, key=str.lower)`: case-insensitive and stable. */
export function sortTags(tags: readonly string[]): string[] {
	return [...tags].sort((a, b) => compareCodePoints(a.toLowerCase(), b.toLowerCase()));
}

/** Lists by name ignoring case, as `get_lists` does (`ORDER BY name COLLATE NOCASE`). */
export function sortLists(lists: Iterable<List>): List[] {
	return [...lists].sort(
		(a, b) => compareNoCase(a.name, b.name) || compareCodePoints(a.uid, b.uid)
	);
}

/** Open items first, then by name, as `get_list_data` does (`ORDER BY done, name COLLATE NOCASE`). */
export function sortItems(items: Iterable<Item>): Item[] {
	return [...items].sort(
		(a, b) =>
			Number(a.done) - Number(b.done) ||
			compareNoCase(a.name, b.name) ||
			compareCodePoints(a.uid, b.uid)
	);
}

/** The items of each list (key: `list_uid`), each sorted with `sortItems`. */
export function groupItemsByList(items: ReadonlyMap<string, Item>): Map<string, Item[]> {
	const groups = new Map<string, Item[]>();
	for (const item of items.values()) {
		const group = groups.get(item.list_uid);
		if (group) group.push(item);
		else groups.set(item.list_uid, [item]);
	}
	for (const [listUid, group] of groups) groups.set(listUid, sortItems(group));
	return groups;
}
