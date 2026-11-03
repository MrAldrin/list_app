// Small rules of the list page, kept out of the components so Vitest can
// test them. They copy what NiceGUI's list page does (`src/main.py`).

import {
	compareCodePoints,
	ITEM_SORTS,
	itemSortChoice,
	type ItemSortChoice
} from '#lib/data/order.ts';
import { itemName, itemNameKey } from '#lib/data/overlay.ts';
import type { Item } from '#lib/data/index.ts';
import type { ToastKind } from '#lib/ui/toasts.svelte.ts';

/** Shown when the list is gone or not in this room. */
export const UNAVAILABLE_LIST_MESSAGE = 'List not found. It may have been deleted.';

/** Shown when the list disappears while its page is open, so it surely was deleted. */
export const DELETED_LIST_MESSAGE = 'This list was deleted.';

/** A share link that opens no list, on load (NiceGUI's text). */
export const SHARE_UNAVAILABLE_MESSAGE = 'This list was deleted or you no longer have access.';

/** A share link that stopped working while its page was open (NiceGUI's text). */
export const SHARE_RESET_MESSAGE = 'This list was deleted or this share link was reset.';

/** How many names the add field suggests; about three show, the rest scroll. */
export const MAX_SUGGESTIONS = 10;

/** Usual items need at least two recorded adds. */
export const USUAL_ITEM_MIN_ADD_COUNT = 2;

/** How many usual items the blank add field offers. */
export const MAX_USUAL_ITEM_SUGGESTIONS = 3;

/** Like the server's item-name display normalization: trim, but keep case. */
export function normalizeItemName(raw: string): string {
	return itemName(raw);
}

/**
 * Names the add field suggests while typing: the list's item names that
 * contain the typed text, most-added first, then by name, at most ten. Hidden
 * checked items count too, so typing finds them and a tap brings them back.
 */
export function itemSuggestions(
	items: readonly Pick<Item, 'name' | 'add_count'>[],
	typed: string
): string[] {
	const text = itemNameKey(typed);
	if (!text) return [];
	// A name listed twice ranks by its highest count.
	const counts = new Map<string, number>();
	for (const { name, add_count } of items) {
		if (itemNameKey(name).includes(text)) {
			counts.set(name, Math.max(counts.get(name) ?? 0, add_count));
		}
	}
	return [...counts]
		.sort(([a, countA], [b, countB]) => countB - countA || compareCodePoints(a, b))
		.map(([name]) => name)
		.slice(0, MAX_SUGGESTIONS);
}

/**
 * Checked items added at least twice, most-added first, for the blank add field.
 * Open items are already on the list and are not shortcuts; typing keeps the
 * existing autocomplete in charge.
 */
export function usualItemSuggestions(
	items: readonly Pick<Item, 'name' | 'done' | 'add_count'>[],
	typed: string
): string[] {
	if (itemNameKey(typed)) return [];
	return items
		.filter((item) => item.done && item.add_count >= USUAL_ITEM_MIN_ADD_COUNT)
		.sort(
			(a, b) =>
				b.add_count - a.add_count ||
				compareCodePoints(itemNameKey(a.name), itemNameKey(b.name)) ||
				compareCodePoints(a.name, b.name)
		)
		.map((item) => item.name)
		.slice(0, MAX_USUAL_ITEM_SUGGESTIONS);
}

/** The toast after adding: NiceGUI's "Added milk" or "Restored milk!". */
export function addFeedback(
	outcome: 'added' | 'restored',
	name: string
): { message: string; kind: ToastKind } {
	return outcome === 'restored'
		? { message: `Restored ${name}!`, kind: 'info' }
		: { message: `Added ${name}`, kind: 'success' };
}

/** The toast after checking or unchecking an item: "Checked milk" or "Unchecked milk", both neutral. */
export function checkFeedback(name: string, done: boolean): { message: string; kind: ToastKind } {
	return { message: `${done ? 'Checked' : 'Unchecked'} ${name}`, kind: 'info' };
}

/** How long "Undo" stays after deleting an item, as NiceGUI's undo bar (5 s). */
export const UNDO_DURATION = 5_000;

/**
 * The "×2" shown after an item's name, so everyone sees a quantity of 2 or
 * more. Null when the quantity is 1, or when the stepper already shows it.
 */
export function quantityBadge(quantity: number, showQuantities: boolean): string | null {
	return quantity > 1 && !showQuantities ? `×${quantity}` : null;
}

const SHOW_QUANTITIES_KEY = 'list-app:show-quantities:';

/** The browser's localStorage, or null where it is blocked (private mode, tests). */
function browserStorage(): Storage | null {
	try {
		return globalThis.localStorage ?? null;
	} catch {
		return null;
	}
}

/**
 * "Show quantities" (the − / + stepper on every row) for one list. A personal
 * setting: saved in this browser only, off when nothing is saved.
 */
export function loadShowQuantities(listUid: string, storage = browserStorage()): boolean {
	try {
		return storage?.getItem(SHOW_QUANTITIES_KEY + listUid) === 'true';
	} catch {
		return false;
	}
}

/** Saves "Show quantities" for one list; does nothing where storage is blocked. */
export function saveShowQuantities(listUid: string, on: boolean, storage = browserStorage()): void {
	try {
		if (on) storage?.setItem(SHOW_QUANTITIES_KEY + listUid, 'true');
		else storage?.removeItem(SHOW_QUANTITIES_KEY + listUid);
	} catch {
		// Storage full or blocked: the switch still works until the page is left.
	}
}

const DAY_FORMAT = new Intl.DateTimeFormat('en-GB', {
	day: 'numeric',
	month: 'short',
	timeZone: 'UTC'
});

/** A date as the list shows it: "18 Oct". Reads the day as written, with no time zone shift. */
export function formatItemDate(date: string): string {
	const [year, month, day] = date.split('-').map(Number);
	const when = new Date(0);
	when.setUTCFullYear(year, month - 1, day);
	return DAY_FORMAT.format(when);
}

/** The dialog's line on how often an item was added: "Added once", "Added 5 times". */
export function addedLabel(count: number): string {
	return count === 1 ? 'Added once' : `Added ${count} times`;
}

/**
 * The dialog's line on when an item was last added, in the browser's local
 * time: "Last added 2026-10-18 14:08". Null when there is no time (items from
 * before the counter) or it is not a valid time.
 */
export function lastAddedLabel(addedAt: string | null): string | null {
	if (addedAt === null) return null;
	const when = new Date(addedAt);
	if (Number.isNaN(when.getTime())) return null;
	const pad = (part: number) => String(part).padStart(2, '0');
	const day = [when.getFullYear(), pad(when.getMonth() + 1), pad(when.getDate())].join('-');
	const time = `${pad(when.getHours())}:${pad(when.getMinutes())}`;
	return `Last added ${day} ${time}`;
}

const SORT_KEY = 'list-app:sort:';

/**
 * The item sort of one list (a choice of `ITEM_SORTS`). A personal setting,
 * saved in this browser only. Name A–Z when nothing valid is saved.
 */
export function loadItemSort(listUid: string, storage = browserStorage()): ItemSortChoice {
	try {
		return itemSortChoice(storage?.getItem(SORT_KEY + listUid)) ?? ITEM_SORTS[0];
	} catch {
		return ITEM_SORTS[0];
	}
}

/** Saves the item sort of one list by its choice id; does nothing where storage is blocked. */
export function saveItemSort(listUid: string, choiceId: string, storage = browserStorage()): void {
	try {
		storage?.setItem(SORT_KEY + listUid, choiceId);
	} catch {
		// Storage full or blocked: the sort still works until the page is left.
	}
}

/** A quantity after − or +; never below 1, like the server. */
export function stepQuantity(quantity: number, delta: number): number {
	return Math.max(1, quantity + delta);
}
