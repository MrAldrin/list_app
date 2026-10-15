// The one room sign-in path. RoomHandle.login and the standalone login both use it.
// Callers plug in what only an open page has (identity epoch, store warnings, refresh).

import type { Api } from './api';
import {
	SIGNIN_LOCK_UNAVAILABLE,
	SIGNIN_STATE_UNAVAILABLE,
	SNAPSHOT_UNAVAILABLE
} from './messages';
import { hasPendingServerLogout, sendServerLogout } from './pending-logout';
import { failed, type ActionResult } from './result';
import {
	announceRoomSignIn,
	withRoomSessionLock,
	type SessionLockManager
} from './session-transition';
import type {
	RoomIdentity,
	SnapshotGeneration,
	SnapshotResult,
	SnapshotStore
} from './snapshot-store';
import type { Room } from './types';

export const SIGNIN_INTERRUPTED = 'Room sign-in was interrupted by sign-out.';

export interface SignInState {
	/** The generation read after sign-in; null without a snapshot store. */
	generation: SnapshotResult<SnapshotGeneration> | null;
	markerCleared: boolean;
}

export interface RoomSignIn {
	slug: string;
	password: string;
	snapshots: SnapshotStore | null;
	client: Pick<Api, 'login' | 'logout'>;
	locks: SessionLockManager | null;
	/** Shows a page warning. A standalone sign-in has no page to warn on. */
	warn?: (message: string) => void;
	/** False once an open page changed identity (sign-out, 401) during sign-in. */
	stillCurrent?: () => boolean;
	/** Clears an open page's access. Called whenever the sign-in is cancelled. */
	block?: () => void;
	onLoginError?: (error: unknown) => void;
	/** Runs after all checks, before the announcement. A result stops the sign-in. */
	complete: (state: SignInState) => Promise<ActionResult<Room> | null>;
	onError?: (error: unknown) => void;
}

const interrupted: ActionResult<Room> = {
	ok: false,
	code: 'signed_out',
	message: SIGNIN_INTERRUPTED
};
const stateUnavailable: ActionResult<Room> = {
	ok: false,
	code: 'session_transition_unavailable',
	message: SIGNIN_STATE_UNAVAILABLE
};
const logoutPending: ActionResult<Room> = {
	ok: false,
	code: 'logout_pending',
	message: SIGNIN_LOCK_UNAVAILABLE
};

/** Signs in after any pending server sign-out, fails closed on newer sign-outs. */
export async function signInRoom(options: RoomSignIn): Promise<ActionResult<Room>> {
	const { slug, password, snapshots, client, locks } = options;
	const identity: RoomIdentity = { kind: 'room', slug };
	const warn = options.warn ?? (() => undefined);
	const warnSnapshot = () => warn(SNAPSHOT_UNAVAILABLE);
	const stillCurrent = options.stillCurrent ?? (() => true);
	const cancel = (): ActionResult<Room> => {
		options.block?.();
		return interrupted;
	};
	const restoreAndCancel = async (): Promise<ActionResult<Room>> => {
		const restored = await snapshots!.localSignOut(identity);
		if (!restored.ok) warnSnapshot();
		return cancel();
	};
	// A session cookie may exist now, but sign-out state cannot be read: clear
	// local access and revoke the new session on a best-effort basis.
	const abortUnreadable = async (): Promise<ActionResult<Room>> => {
		options.block?.();
		try {
			const marked = await snapshots!.localSignOut(identity);
			if (!marked.ok) warnSnapshot();
		} catch {
			warnSnapshot();
		}
		try {
			await client.logout(slug);
		} catch {
			// Local access stays blocked even if the best-effort server logout fails.
		}
		return stateUnavailable;
	};

	const transition = async (): Promise<ActionResult<Room>> => {
		let markerCleared = false;
		let before: SnapshotGeneration | null = null;
		if (snapshots) {
			let pending;
			try {
				pending = await snapshots.pendingServerLogouts();
			} catch {
				pending = null;
			}
			if (!pending?.ok) {
				warnSnapshot();
				return stateUnavailable;
			}
			if (pending.value.some((entry) => entry.slug === slug)) {
				if (!locks) return logoutPending;
				try {
					if (!(await sendServerLogout(slug, identity, snapshots, client)).ok) return logoutPending;
				} catch {
					return logoutPending;
				}
			}
		}
		if (!stillCurrent()) return cancel();
		if (snapshots) {
			const cleared = await snapshots.clearSignOutAfterSignIn(identity);
			markerCleared = cleared.ok;
			if (!cleared.ok) warnSnapshot();
			const current = await snapshots.generation(identity);
			if (!current.ok && current.reason === 'signed_out') return restoreAndCancel();
			if (current.ok) before = current.value;
			else warnSnapshot();
		}
		let room: Room;
		try {
			room = await client.login(slug, password);
		} catch (error) {
			options.onLoginError?.(error);
			return failed(error);
		}
		if (!stillCurrent()) {
			if (snapshots) return restoreAndCancel();
			return cancel();
		}
		let generation: SignInState['generation'] = null;
		if (snapshots) {
			let pending;
			try {
				pending = await snapshots.pendingServerLogouts();
			} catch {
				return abortUnreadable();
			}
			if (!pending.ok) return abortUnreadable();
			if (pending.value.some((entry) => entry.slug === slug)) return restoreAndCancel();
			generation = await snapshots.generation(identity);
			if (!generation.ok && generation.reason === 'signed_out') return restoreAndCancel();
			if (
				before &&
				generation.ok &&
				(generation.value.identityKey !== before.identityKey ||
					generation.value.generation !== before.generation)
			) {
				return restoreAndCancel();
			}
		}
		const stopped = await options.complete({ generation, markerCleared });
		if (stopped) return stopped;
		announceRoomSignIn(slug);
		return { ok: true, result: room };
	};

	try {
		const locked = await withRoomSessionLock(slug, transition, locks);
		if (locked.acquired) return locked.value!;
		if (snapshots && (await hasPendingServerLogout(snapshots, slug, warnSnapshot))) {
			warn(SIGNIN_LOCK_UNAVAILABLE);
			return logoutPending;
		}
		// Ordinary first sign-in remains usable without Web Locks. The durable
		// marker is rechecked before and after the request; pending logout fails closed.
		return await transition();
	} catch (error) {
		options.onError?.(error);
		return failed(error);
	}
}
