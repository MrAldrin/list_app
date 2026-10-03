// Reads a room slug from what the user pasted on the start page: a full room
// link (`https://…/room/home-ab12cd`, also `/app/room/…`) or just the code.
// Same rule as NiceGUI's start page: the last part of the link's path.

/** The room slug, or null when the text has none. */
export function roomSlugFromInput(raw: string): string | null {
	let text = raw.trim();
	// Drop the "#…" and "?…" parts, like Python's `urlsplit` does.
	text = text.split('#')[0].split('?')[0];
	// Drop "https://host" (or "//host"), so the host is never taken as the slug.
	text = text.replace(/^([a-z][a-z0-9+.-]*:)?\/\/[^/]*/i, '');
	const parts = text.replace(/\/+$/, '').split('/');
	const slug = parts[parts.length - 1];
	return slug ? slug : null;
}
