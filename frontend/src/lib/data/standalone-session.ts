// Sign-in and sign-out for a room with no open RoomHandle on this page.
// Also owns the browser snapshot store, which RoomHandle and lastRoom share.

import type { Api } from './api';
import { LOGOUT_LOCAL_CLEAR_UNCONFIRMED } from './messages';
import { finishServerSignOut } from './pending-logout';
import type { ActionResult } from './result';
import { signInRoom } from './room-signin';
import { browserSessionLocks } from './session-transition';
import { createSnapshotStore, type RoomIdentity, type SnapshotStore } from './snapshot-store';
import type { Room } from './types';

let defaultSnapshots: SnapshotStore | null = null;
const volatileSignIns = new Set<string>();

export function browserSnapshots(): SnapshotStore {
	defaultSnapshots ??= createSnapshotStore({
		channel: typeof window === 'undefined' ? null : undefined
	});
	return defaultSnapshots;
}

/** True once if this room was signed in while its sign-out marker could not be cleared. */
export function takeVolatileSignIn(slug: string): boolean {
	return volatileSignIns.delete(slug);
}

export async function standaloneLogin(
	slug: string,
	password: string,
	client: Api
): Promise<ActionResult<Room>> {
	return signInRoom({
		slug,
		password,
		snapshots: browserSnapshots(),
		client,
		locks: browserSessionLocks(),
		// No page is open yet: the next RoomHandle for this slug picks this up.
		complete: async ({ generation, markerCleared }) => {
			if (!markerCleared || !generation?.ok) volatileSignIns.add(slug);
			return null;
		}
	});
}

/** Clears saved data first, then attempts the server sign-out. */
export async function standaloneLogout(slug: string, client: Api): Promise<ActionResult> {
	const snapshots = browserSnapshots();
	const identity: RoomIdentity = { kind: 'room', slug };
	let marked = false;
	try {
		marked = (await snapshots.localSignOut(identity)).ok;
	} catch {
		// The visible room is already gone; do not race a newer sign-in with DELETE.
	}
	if (!marked)
		return { ok: false, code: 'local_clear_unconfirmed', message: LOGOUT_LOCAL_CLEAR_UNCONFIRMED };
	return finishServerSignOut({
		slug,
		identity,
		snapshots,
		client,
		locks: browserSessionLocks()
	});
}
