// Sign-in and sign-out for a room with no open RoomHandle on this page.
// Also owns the browser snapshot store, which RoomHandle and lastRoom share.

import type { Api } from './api';
import {
	LOGOUT_LOCAL_CLEAR_UNCONFIRMED,
	LOGOUT_MARKER_UNACKNOWLEDGED,
	LOGOUT_SERVER_PENDING,
	SIGNIN_LOCK_UNAVAILABLE,
	SIGNIN_STATE_UNAVAILABLE,
	SNAPSHOT_UNAVAILABLE
} from './messages';
import { isPendingFor } from './pending-logout';
import { failed, type ActionResult } from './result';
import { announceRoomSignIn, browserSessionLocks, withRoomSessionLock } from './session-transition';
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
	const snapshots = browserSnapshots();
	const locks = browserSessionLocks();
	const signIn = async (): Promise<ActionResult<Room>> => {
		let pending;
		try {
			pending = await snapshots.pendingServerLogouts();
		} catch {
			return {
				ok: false,
				code: 'session_transition_unavailable',
				message: SIGNIN_STATE_UNAVAILABLE
			};
		}
		if (!pending.ok) {
			return {
				ok: false,
				code: 'session_transition_unavailable',
				message: SIGNIN_STATE_UNAVAILABLE
			};
		}
		if (pending.value.some((identity) => identity.slug === slug)) {
			if (!locks) return { ok: false, code: 'logout_pending', message: SIGNIN_LOCK_UNAVAILABLE };
			try {
				await client.logout(slug);
				const ack = await snapshots.acknowledgeServerLogout({ kind: 'room', slug });
				if (!ack.ok) return { ok: false, code: 'storage', message: SNAPSHOT_UNAVAILABLE };
			} catch (error) {
				return failed(error);
			}
		}
		const identity: RoomIdentity = { kind: 'room', slug };
		const markerCleared = await snapshots.clearSignOutAfterSignIn(identity);
		const baseline = await snapshots.generation(identity);
		if (!baseline.ok && baseline.reason === 'signed_out') {
			return { ok: false, code: 'logout_pending', message: SIGNIN_LOCK_UNAVAILABLE };
		}
		try {
			const room = await client.login(slug, password);
			const pendingAfter = await snapshots.pendingServerLogouts();
			if (!pendingAfter.ok) {
				await snapshots.localSignOut(identity);
				await client.logout(slug).catch(() => undefined);
				return {
					ok: false,
					code: 'session_transition_unavailable',
					message: SIGNIN_STATE_UNAVAILABLE
				};
			}
			const current = await snapshots.generation(identity);
			if (
				pendingAfter.value.some((entry) => entry.slug === slug) ||
				(!current.ok && current.reason === 'signed_out') ||
				(baseline.ok &&
					current.ok &&
					(current.value.identityKey !== baseline.value.identityKey ||
						current.value.generation !== baseline.value.generation))
			) {
				await snapshots.localSignOut(identity);
				return {
					ok: false,
					code: 'signed_out',
					message: 'Room sign-in was interrupted by sign-out.'
				};
			}
			if (!markerCleared.ok || !current.ok) volatileSignIns.add(slug);
			announceRoomSignIn(slug);
			return { ok: true, result: room };
		} catch (error) {
			return failed(error);
		}
	};
	try {
		const locked = await withRoomSessionLock(slug, signIn, locks);
		if (locked.acquired) return locked.value!;
		const pending = await snapshots.pendingServerLogouts();
		if (isPendingFor(pending, slug)) {
			return { ok: false, code: 'logout_pending', message: SIGNIN_LOCK_UNAVAILABLE };
		}
		return await signIn();
	} catch (error) {
		return failed(error);
	}
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
	const locks = browserSessionLocks();
	if (!marked)
		return { ok: false, code: 'local_clear_unconfirmed', message: LOGOUT_LOCAL_CLEAR_UNCONFIRMED };
	if (!locks) return { ok: false, code: 'server_logout_pending', message: LOGOUT_SERVER_PENDING };
	let serverSignedOut = false;
	try {
		const locked = await withRoomSessionLock(
			slug,
			async () => {
				const pending = await snapshots.pendingServerLogouts();
				if (!isPendingFor(pending, slug)) return false;
				const generation = await snapshots.generation(identity);
				if (generation.ok || generation.reason !== 'signed_out') return false;
				await client.logout(slug);
				serverSignedOut = true;
				return (await snapshots.acknowledgeServerLogout(identity)).ok;
			},
			locks
		);
		if (locked.acquired && locked.value) return { ok: true, result: {} };
		return serverSignedOut
			? { ok: false, code: 'logout_marker_unacknowledged', message: LOGOUT_MARKER_UNACKNOWLEDGED }
			: { ok: false, code: 'server_logout_pending', message: LOGOUT_SERVER_PENDING };
	} catch {
		return serverSignedOut
			? { ok: false, code: 'logout_marker_unacknowledged', message: LOGOUT_MARKER_UNACKNOWLEDGED }
			: { ok: false, code: 'server_logout_pending', message: LOGOUT_SERVER_PENDING };
	}
}
