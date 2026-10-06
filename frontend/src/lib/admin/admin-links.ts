// Links between the admin page and rooms. `?admin=true` keeps the NiceGUI link
// shape; it never gives room access. The room page's "Back to admin" follows
// the admin sign-in, not this query.

import { resolve } from '$app/paths';

export const ADMIN_QUERY = 'admin=true';

export function adminRoomHref(slug: string): string {
	return `${resolve('/room/[slug]', { slug })}?${ADMIN_QUERY}`;
}
