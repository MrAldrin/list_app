// Text and links for creation invitations on the admin page, as NiceGUI
// shows them (`src/ui/room_invitations.py`).

import { resolve } from '$app/paths';
import type { Invitation } from '#lib/data/index.ts';
import { absoluteUrl } from '#lib/ui/share.ts';

/** "2026-10-05 09:12 UTC" from a UTC ISO time. */
export function formatUtc(iso: string): string {
	const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(iso);
	return match ? `${match[1]} ${match[2]} UTC` : iso;
}

/** "Active", "Revoked" or "Expired". */
export function statusLabel(status: Invitation['status']): string {
	return status.charAt(0).toUpperCase() + status.slice(1);
}

/** The full link to send: anyone with it can create a room. */
export function invitationUrl(token: string, origin?: string): string {
	return absoluteUrl(resolve('/create-room/[token]', { token }), origin);
}
