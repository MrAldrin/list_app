// Rows checked or unchecked a moment ago keep their place on screen, so the
// row under the thumb does not slide away on the next tap. Pure rules, so
// Vitest can test them; the list page does the timing.

/** How long after the last tap the rows wait before they move to their sorted place. */
export const HOLD_MS = 1500;

/**
 * The rows in the order to show. Rows in `held` keep the place they had in
 * `shown` (the order on screen when the hold began). The other rows fill the
 * remaining places in `sorted` order. A held row that is no longer listed is
 * left out, and a row that is new takes a free place.
 */
export function holdRowOrder<T extends { uid: string }>(
	sorted: readonly T[],
	shown: readonly string[],
	held: ReadonlySet<string>
): T[] {
	const byUid = new Map(sorted.map((item) => [item.uid, item]));
	const result: (T | undefined)[] = new Array(sorted.length);
	const placed = new Set<string>();
	shown.forEach((uid, index) => {
		const item = byUid.get(uid);
		if (!held.has(uid) || !item || index >= result.length) return;
		result[index] = item;
		placed.add(uid);
	});
	let slot = 0;
	for (const item of sorted) {
		if (placed.has(item.uid)) continue;
		while (result[slot] !== undefined) slot += 1;
		result[slot] = item;
	}
	return result as T[];
}
