import { compareCodePoints } from '#lib/data/order.ts';
import { itemNameKey } from '#lib/data/overlay.ts';

/** The item limit enforced by the room group API. */
export const MAX_GROUP_ITEM_COUNT = 1_000;

/** How many room item names to offer while editing a group. */
export const MAX_GROUP_ITEM_SUGGESTIONS = 5;

/**
 * Existing names from the current room that match the typed text and are not
 * already in the group. Callers provide room-local item data; this helper does
 * not fetch or retain names from other rooms.
 */
export function itemGroupSuggestions(
	roomItemNames: readonly string[],
	groupItems: readonly string[],
	typed: string
): string[] {
	const text = itemNameKey(typed);
	if (!text) return [];

	const existing = new Set(groupItems.map(itemNameKey));
	const names = new Map<string, string>();
	for (const name of roomItemNames) {
		const key = itemNameKey(name);
		if (key && !existing.has(key) && key.includes(text) && !names.has(key)) {
			names.set(key, name);
		}
	}

	return [...names.values()].sort(compareCodePoints).slice(0, MAX_GROUP_ITEM_SUGGESTIONS);
}
