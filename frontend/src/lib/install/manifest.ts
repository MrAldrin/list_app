// Which install manifest a page links, as NiceGUI does
// (docs/home-screen-installation.md). The manifest's `start_url` is the
// address a home-screen icon opens:
// - the room page links its room's manifest, so the icon opens that room;
// - every other page (start, list, share, admin, invitation) links the
//   default manifest, which opens the start page and so the last room.
// Only the public room slug goes into the address: never `?admin=true`,
// passwords, tokens, share or invitation links.

/** The room page's route id. */
export const ROOM_ROUTE = '/room/[slug]';

/** The manifest address for a page, from its route id and parameters. */
export function manifestHref(
	routeId: string | null,
	params: Partial<Record<string, string>>,
	base: string
): string {
	const slug = params.slug;
	if (routeId === ROOM_ROUTE && slug) {
		return `${base}/room-manifest/${encodeURIComponent(slug)}.webmanifest`;
	}
	return `${base}/manifest.webmanifest`;
}
