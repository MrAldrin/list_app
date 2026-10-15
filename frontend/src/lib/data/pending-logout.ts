// Server sign-outs that could not finish yet. The pending list lives in the snapshot store.
// Callers own the snapshot warning: they pass `warn` instead of touching RoomHandle state.

import type { Api } from './api';
import { LOGOUT_MARKER_UNACKNOWLEDGED, LOGOUT_SERVER_PENDING } from './messages';
import type { ActionResult } from './result';
import { withRoomSessionLock, type SessionLockManager } from './session-transition';
import type { RoomIdentity, SnapshotStore } from './snapshot-store';

type PendingRead = Awaited<ReturnType<SnapshotStore['pendingServerLogouts']>>;

/** True when a pending-list read names this slug. A failed read counts as not pending. */
export function isPendingFor(pending: PendingRead, slug: string): boolean {
	return pending.ok && pending.value.some((identity) => identity.slug === slug);
}

/** True when this slug has a pending server sign-out. Calls `warn` when the list cannot be read. */
export async function hasPendingServerLogout(
	snapshots: Pick<SnapshotStore, 'pendingServerLogouts'>,
	slug: string,
	warn: () => void
): Promise<boolean> {
	try {
		const pending = await snapshots.pendingServerLogouts();
		if (!pending.ok) {
			warn();
			return false;
		}
		return pending.value.some((identity) => identity.slug === slug);
	} catch {
		warn();
		return false;
	}
}

/**
 * Sends a pending server sign-out and acknowledges it. The caller holds the room
 * session lock (or runs without locks) and has checked that the slug is pending.
 */
export async function sendServerLogout(
	slug: string,
	identity: RoomIdentity,
	snapshots: Pick<SnapshotStore, 'acknowledgeServerLogout'>,
	client: Pick<Api, 'logout'>
): Promise<Awaited<ReturnType<SnapshotStore['acknowledgeServerLogout']>>> {
	await client.logout(slug);
	return snapshots.acknowledgeServerLogout(identity);
}

export interface PendingLogoutRetry {
	slug: string;
	identity: RoomIdentity;
	snapshots: Pick<SnapshotStore, 'pendingServerLogouts' | 'acknowledgeServerLogout'>;
	api: Pick<Api, 'logout'>;
	locks: SessionLockManager | null;
	warn: () => void;
}

/** Replays a pending server sign-out under the room session lock. True when it is no longer pending. */
export async function retryPendingServerLogout(options: PendingLogoutRetry): Promise<boolean> {
	const { slug, identity, snapshots, api, locks, warn } = options;
	let pending;
	try {
		pending = await snapshots.pendingServerLogouts();
	} catch {
		warn();
		return false;
	}
	if (!pending.ok) {
		warn();
		return false;
	}
	if (!pending.value.some((entry) => entry.slug === slug)) return false;
	const attempt = async () => {
		const latest = await snapshots.pendingServerLogouts();
		if (!latest.ok) return false;
		if (!latest.value.some((entry) => entry.slug === slug)) return true;
		try {
			const acknowledged = await sendServerLogout(slug, identity, snapshots, api);
			if (!acknowledged.ok) warn();
			return acknowledged.ok;
		} catch {
			return false;
		}
	};
	try {
		const locked = await withRoomSessionLock(slug, attempt, locks);
		if (!locked.acquired) return false;
		return locked.value ?? false;
	} catch {
		return false;
	}
}

export interface ServerSignOut {
	slug: string;
	identity: RoomIdentity;
	snapshots: Pick<SnapshotStore, 'pendingServerLogouts' | 'generation' | 'acknowledgeServerLogout'>;
	client: Pick<Api, 'logout'>;
	locks: SessionLockManager | null;
	/** Receives a warning for an answered failure. A thrown failure does not call it. */
	warn?: (message: string) => void;
}

/**
 * The server half of a user sign-out. The caller has already stored the local
 * sign-out marker. Sends the server sign-out only while the marker is still
 * pending and the local state is still signed out, then acknowledges it.
 */
export async function finishServerSignOut(options: ServerSignOut): Promise<ActionResult> {
	const { slug, identity, snapshots, client, locks, warn } = options;
	if (!locks) {
		warn?.(LOGOUT_SERVER_PENDING);
		return { ok: false, code: 'server_logout_pending', message: LOGOUT_SERVER_PENDING };
	}
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
				const acknowledged = await snapshots.acknowledgeServerLogout(identity);
				return acknowledged.ok;
			},
			locks
		);
		if (locked.acquired && locked.value) return { ok: true, result: {} };
		const code = serverSignedOut ? 'logout_marker_unacknowledged' : 'server_logout_pending';
		const message = serverSignedOut ? LOGOUT_MARKER_UNACKNOWLEDGED : LOGOUT_SERVER_PENDING;
		warn?.(message);
		return { ok: false, code, message };
	} catch {
		// A failed request stays pending and is retried when the room opens again.
		return serverSignedOut
			? { ok: false, code: 'logout_marker_unacknowledged', message: LOGOUT_MARKER_UNACKNOWLEDGED }
			: { ok: false, code: 'server_logout_pending', message: LOGOUT_SERVER_PENDING };
	}
}
