// Links between the admin page and rooms. `?admin=true` keeps the NiceGUI link
// shape; it never gives room access or changes the room header.

import { resolve } from '$app/paths';

export const ADMIN_QUERY = 'admin=true';

export function adminRoomHref(slug: string): string {
	return `${resolve('/room/[slug]', { slug })}?${ADMIN_QUERY}`;
}
