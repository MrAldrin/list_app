// Links between the admin page and rooms. `?admin=true` only adds a way back
// to the admin page on the room page; it never gives room access.

import { resolve } from '$app/paths';

export const ADMIN_QUERY = 'admin=true';

export function adminRoomHref(slug: string): string {
	return `${resolve('/room/[slug]', { slug })}?${ADMIN_QUERY}`;
}

/** True when the room page was opened from the admin page. */
export function openedFromAdmin(url: {
	searchParams: { get(name: string): string | null };
}): boolean {
	return url.searchParams.get('admin') === 'true';
}
