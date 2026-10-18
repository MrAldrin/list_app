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

/** What the item list can be sorted by. Each key has its own rule in `ITEM_SORTS`. */
export type ItemSortKey = 'name' | 'date' | 'added' | 'most-added';

/** A sort key and whether it runs the other way. `reverse: false` is the default direction. */
export interface ItemSort {
	key: ItemSortKey;
	reverse: boolean;
}

/** One choice of the Sort menu. `id` is what is saved in the browser. */
export interface ItemSortChoice extends ItemSort {
	id: string;
	label: string;
}

/**
 * Every sort choice, first one is the default (name A–Z, as before sorting).
 * Open items always come before checked ones, whatever the choice.
 */
export const ITEM_SORTS: readonly ItemSortChoice[] = [
	{ id: 'name-asc', label: 'Name A–Z', key: 'name', reverse: false },
	{ id: 'name-desc', label: 'Name Z–A', key: 'name', reverse: true },
	{ id: 'date-asc', label: 'Date: soonest first', key: 'date', reverse: false },
	{ id: 'date-desc', label: 'Date: latest first', key: 'date', reverse: true },
	{ id: 'added-desc', label: 'Added: newest first', key: 'added', reverse: false },
	{ id: 'added-asc', label: 'Added: oldest first', key: 'added', reverse: true },
	{ id: 'most-added-desc', label: 'Most added first', key: 'most-added', reverse: false },
	{ id: 'most-added-asc', label: 'Fewest added first', key: 'most-added', reverse: true }
];

/** The default choice: name A–Z. */
export const DEFAULT_ITEM_SORT: ItemSort = { key: 'name', reverse: false };

/** The choice with this id, or null when there is none. */
export function itemSortChoice(id: string | null | undefined): ItemSortChoice | null {
	return ITEM_SORTS.find((choice) => choice.id === id) ?? null;
}

/** Turns a key's first-direction comparison into the chosen direction. */
function directed(diff: number, reverse: boolean): number {
	return reverse ? -diff : diff;
}

/** Numbers in order; `-Infinity` (no time) is fine. */
function compareNumbers(a: number, b: number): number {
	return a < b ? -1 : a > b ? 1 : 0;
}

/** The time an item was added, or `-Infinity` when it has none (so it counts as oldest). */
function addedTime(item: Item): number {
	return item.added_at === null ? -Infinity : Date.parse(item.added_at);
}

/** The rule of each key, without the ties (`sortItems` adds name A–Z and then the uid). */
const KEY_RULES: Record<ItemSortKey, (a: Item, b: Item, reverse: boolean) => number> = {
	name: (a, b, reverse) => directed(compareNoCase(a.name, b.name), reverse),
	// Items with a date come first in both directions; without a date they go last.
	date: (a, b, reverse) => {
		if (a.date === null || b.date === null) {
			return Number(a.date === null) - Number(b.date === null);
		}
		return directed(compareCodePoints(a.date, b.date), reverse);
	},
	// The default is newest first. An item with no time is the oldest.
	added: (a, b, reverse) => directed(compareNumbers(addedTime(b), addedTime(a)), reverse),
	'most-added': (a, b, reverse) => directed(compareNumbers(b.add_count, a.add_count), reverse)
};

/**
 * Open items first, then by the chosen sort. Ties are broken by name A–Z,
 * so the order never jumps around. The default is name A–Z, as
 * `get_list_data` does (`ORDER BY done, name COLLATE NOCASE`).
 */
export function sortItems(items: Iterable<Item>, sort: ItemSort = DEFAULT_ITEM_SORT): Item[] {
	const rule = KEY_RULES[sort.key];
	return [...items].sort(
		(a, b) =>
			Number(a.done) - Number(b.done) ||
			rule(a, b, sort.reverse) ||
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
