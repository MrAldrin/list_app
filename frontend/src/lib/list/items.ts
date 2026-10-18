// Small rules of the list page, kept out of the components so Vitest can
// test them. They copy what NiceGUI's list page does (`src/main.py`).

import { compareCodePoints } from '#lib/data/order.ts';
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

/** How many names the add field suggests, as in NiceGUI. */
export const MAX_SUGGESTIONS = 3;

/** Like Python's `normalize_item_name`: outer spaces removed, lowercase. */
export function normalizeItemName(raw: string): string {
	return raw.trim().toLowerCase();
}

/**
 * Names the add field suggests while typing: the list's item names that
 * contain the typed text, sorted, at most three. Hidden checked items count
 * too, so typing finds them and a tap brings them back.
 */
export function itemSuggestions(items: readonly Pick<Item, 'name'>[], typed: string): string[] {
	const text = normalizeItemName(typed);
	if (!text) return [];
	const names = [...new Set(items.map((item) => item.name))].sort(compareCodePoints);
	return names.filter((name) => name.toLowerCase().includes(text)).slice(0, MAX_SUGGESTIONS);
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

/** A quantity after − or +; never below 1, like the server. */
export function stepQuantity(quantity: number, delta: number): number {
	return Math.max(1, quantity + delta);
}
