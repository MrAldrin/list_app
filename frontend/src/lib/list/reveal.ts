// Opening an item from the due bell: the list page gets `?item=<uid>&at=<ms>`.
// The time makes every tap a new reveal, even to the item already shown.

export interface Reveal {
	/** The item to show. */
	uid: string;
	/** Changes with each tap, so the same item can be revealed again. */
	key: string;
}

/** The link to a list page (or the current page, when `path` is empty) that reveals `itemUid`. */
export function revealHref(path: string, itemUid: string, at = Date.now()): string {
	return `${path}?item=${encodeURIComponent(itemUid)}&at=${at}`;
}

/** The reveal in a page's URL, or null when the URL asks for none. */
export function readReveal(params: { get(name: string): string | null }): Reveal | null {
	const uid = params.get('item');
	if (!uid) return null;
	return { uid, key: `${uid}@${params.get('at') ?? ''}` };
}
