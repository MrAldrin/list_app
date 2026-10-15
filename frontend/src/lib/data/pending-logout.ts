// Server sign-outs that could not finish yet. The pending list lives in the snapshot store.
// Callers own the snapshot warning: they pass `warn` instead of touching RoomHandle state.

import type { Api } from './api';
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
			await api.logout(slug);
			const acknowledged = await snapshots.acknowledgeServerLogout(identity);
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
