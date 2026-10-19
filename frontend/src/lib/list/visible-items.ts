// The items a list page shows, in order: the search (or the hide-done rule),
// then the tag filter, then the sort, then the rows held in place after a tap.
// Pure rules, so Vitest can test them; ListView.svelte only feeds them state.

import type { Item } from '#lib/data/index.ts';
import { sortItems, type ItemSortChoice } from '#lib/data/order.ts';
import { holdRowOrder } from './hold-order.ts';
import { searchItems } from './search.ts';
import { filterByTags } from './tags.ts';

export interface VisibleItemsInput {
	/** Every item of the list, checked or not. */
	all: readonly Item[];
	/** The items the hide-done rule keeps. Called only when no search applies. */
	notHidden: () => readonly Item[];
	/** The add field's text. */
	searchText: string;
	/** True for a saved or unconfirmed view: typing then filters the list. Online it only suggests. */
	filtersBySearch: boolean;
	/** The tag filter: the items must have every one of these tags. */
	tags: readonly string[];
	sort: ItemSortChoice;
	/** Rows to keep in place (see `holdRowOrder`), or null. */
	hold: { shown: readonly string[]; uids: ReadonlySet<string> } | null;
}

/** The rows to show, in order. */
export function visibleItems(input: VisibleItemsInput): Item[] {
	const searching = input.filtersBySearch && input.searchText.trim() !== '';
	const items = searching ? searchItems(input.all, input.searchText) : input.notHidden();
	// Sorted last, after the search and the tag filter (open items still first).
	const sorted = sortItems(filterByTags(items, input.tags), input.sort);
	return input.hold ? holdRowOrder(sorted, input.hold.shown, input.hold.uids) : sorted;
}
