// Small rules of the list page, kept out of the components so Vitest can
// test them. They copy what NiceGUI's list page does (`src/main.py`).

import { compareCodePoints } from '#lib/data/order.ts';
import type { Item } from '#lib/data/index.ts';
import type { ToastKind } from '#lib/ui/toasts.svelte.ts';

/** Shown when the list is gone or not in this room. */
export const UNAVAILABLE_LIST_MESSAGE = 'This list was deleted or is not in this room.';

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

/** How long "Undo" stays after deleting an item, as NiceGUI's undo bar (5 s). */
export const UNDO_DURATION = 5_000;

/** View options of the list page ("Options"). They are not saved, as in NiceGUI. */
export interface QuantityView {
	/** "Show quantities": the − / + stepper on each row. */
	showQuantities: boolean;
	/** "Only show minimum 2": the stepper only for quantities of 2 or more. */
	onlyAboveOne: boolean;
}

/** Whether a row shows its quantity stepper. */
export function showsQuantity(quantity: number, view: QuantityView): boolean {
	return view.showQuantities && (!view.onlyAboveOne || quantity > 1);
}

/** A quantity after − or +; never below 1, like the server. */
export function stepQuantity(quantity: number, delta: number): number {
	return Math.max(1, quantity + delta);
}
