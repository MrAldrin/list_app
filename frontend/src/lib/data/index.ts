// The client data layer: the one entry point for pages and components.
//
//   const room = openRoom(slug);       // start: load data, live updates
//   room.store.lists                   // reactive data (see RoomStore)
//   await room.addItem(list, 'milk');  // writes: { ok, result } or { ok: false, message }
//   closeRoom(room);                   // stop live updates
//
//   const shared = openShare(token);   // a share link: one list, same API
//   await admin.login(password);       // admin: sign-in, rooms, password reset, invitations
//   await invitation.createRoom(…);    // a creation invitation link
//
// Components never call `fetch` themselves.

import { Api, api as defaultApi } from './api';
import {
	LiveUpdates,
	RECONNECT_DELAYS,
	type EventSourceFactory,
	type SessionState
} from './events';
import { newId } from './ids';
import { failed, type ActionResult } from './result';
import { createRoomStore, RoomStore, type RoomStatus } from './room-store.svelte';
import { ShareApi } from './share';
import {
	announceRoomSignIn,
	browserSessionLocks,
	onRoomSignIn,
	withRoomSessionLock,
	type SessionLockManager
} from './session-transition';
import {
	createSnapshotStore,
	type RoomIdentity,
	type SnapshotData,
	type SnapshotGeneration,
	type SnapshotIdentity,
	type SnapshotStore
} from './snapshot-store';
import { ApiError } from './types';
import type {
	HideDone,
	Item,
	ItemAddResult,
	ItemRestoreResult,
	List,
	ListCreateResult,
	Op,
	Room,
	ShareLink
} from './types';
import { WriteQueue } from './write-queue';

export * from './types';
export type { ActionResult } from './result';
export * as admin from './admin';
export * as invitation from './invitation';
export type { RoomStatus, Notice } from './room-store.svelte';
export type { LiveState } from './events';
export { connectionStatus, CONNECTION_STATUS_DELAY, type ConnectionStatus } from './status';
export { RoomStore } from './room-store.svelte';
export { filterVisibleItems, DEFAULT_HIDE_DONE, MAX_HIDE_DONE_COUNT } from './visibility';
export { sortItems, sortLists, sortTags } from './order';
export { newId } from './ids';

let defaultSnapshots: SnapshotStore | null = null;
const volatileSignIns = new Set<string>();

function browserSnapshots(): SnapshotStore {
	defaultSnapshots ??= createSnapshotStore({
		channel: typeof window === 'undefined' ? null : undefined
	});
	return defaultSnapshots;
}

type ListRef = Pick<List, 'uid'>;
type ItemRef = Pick<Item, 'uid' | 'list_uid'>;

/** The API calls a room needs; tests pass a fake. */
export type RoomApi = Pick<
	Api,
	| 'changes'
	| 'sendOp'
	| 'login'
	| 'logout'
	| 'whoAmI'
	| 'eventsUrl'
	| 'changePassword'
	| 'deleteRoom'
	| 'shareLink'
	| 'resetShareLink'
>;

export interface RoomOptions {
	api?: RoomApi;
	/** For `openShare`: the client its share endpoints use. */
	shareApi?: ConstructorParameters<typeof ShareApi>[0];
	createEventSource?: EventSourceFactory;
	retryDelays?: readonly number[];
	reconnectDelays?: readonly number[];
	visibility?: Pick<
		Document,
		'visibilityState' | 'addEventListener' | 'removeEventListener'
	> | null;
	online?: Pick<Window, 'addEventListener' | 'removeEventListener'> | null;
	/** Injectable persistence boundary. `null` disables snapshots for this handle. */
	snapshotStore?: SnapshotStore | null;
	/** Saved views stay unexposed by default until the UI supplies read-only controls. */
	hydrateSavedView?: boolean;
	/** Injectable Web Locks boundary for session-transition tests. */
	sessionLocks?: SessionLockManager | null;
}

const READ_ONLY = {
	ok: false as const,
	code: 'read_only',
	message: 'Saved data is read-only until room access is refreshed.'
};
const SIGNIN_LOCK_UNAVAILABLE =
	'Room sign-in is waiting for a pending sign-out to finish. Reopen this page in a supported secure browser and try again.';
const SIGNIN_STATE_UNAVAILABLE =
	'Room sign-in is blocked because pending sign-out state could not be read. Allow local storage, then retry.';
const SIGNIN_REFRESH_FAILED =
	'Room access could not be confirmed. The app will retry before enabling changes.';
const SNAPSHOT_UNAVAILABLE = 'Saved data could not be updated on this device.';
const LOGOUT_SERVER_PENDING =
	'This sign-out cleared the visible room and its prior saved copy, but server sign-out is pending. A newer sign-in may have restored access; the room cookie may still work. Retry in a secure browser with Web Locks.';
const LOGOUT_LOCAL_CLEAR_UNCONFIRMED =
	'Room data was cleared from this page, but saved data could not be confirmed cleared on this device. Server sign-out was not attempted; the room cookie may still work.';
const LOGOUT_MARKER_UNACKNOWLEDGED =
	'Server sign-out succeeded and its cookie was cleared, but the local sign-out marker could not be acknowledged. Room access stays blocked until the marker can be resolved.';
const PENDING_OPERATION_NOTICE =
	'A change may still be saving. Sign in again to check its status before retrying it.';

/** One room or one share link: committed data, queue, and live updates. */
export class RoomHandle {
	readonly slug: string;
	readonly store: RoomStore;
	readonly #api: RoomApi;
	readonly #queue: WriteQueue;
	readonly #live: LiveUpdates;
	readonly #snapshotStore: SnapshotStore | null;
	readonly #identity: SnapshotIdentity;
	readonly #locks: SessionLockManager | null;
	readonly #isShare: boolean;
	readonly #hydrateSavedView: boolean;
	/** Deleted items, kept so `restoreItem` can bring them back. */
	readonly #deleted = new Map<string, Item>();
	readonly #removeClearHint: (() => void) | null;
	readonly #removeSigninHint: () => void;
	/** An open password change: session checks wait for it. */
	#passwordChange: Promise<unknown> | null = null;
	#users = 0;
	#snapshotGeneration: SnapshotGeneration | null = null;
	#identityEpoch = 0;
	#sessionValidated = false;
	#signoutBlocked = false;
	#volatileAuthorized = false;
	#localSignoutInProgress = false;
	#transitionError: string | null = null;
	#revalidationAttempt = 0;
	#revalidationTimer: ReturnType<typeof setTimeout> | null = null;

	constructor(slug: string, options: RoomOptions = {}) {
		this.slug = slug;
		this.#api = options.api ?? defaultApi;
		this.#isShare = this.#api instanceof ShareApi;
		this.#identity = this.#isShare ? { kind: 'share', token: slug } : { kind: 'room', slug };
		if (this.#identity.kind === 'room') {
			this.#volatileAuthorized = volatileSignIns.delete(slug);
		}
		this.#snapshotStore =
			options.snapshotStore === undefined ? browserSnapshots() : options.snapshotStore;
		this.#locks = options.sessionLocks === undefined ? browserSessionLocks() : options.sessionLocks;
		this.#hydrateSavedView = options.hydrateSavedView ?? false;
		this.store = createRoomStore(slug, this.#api, {
			beforeApply: () => this.#identityStillCurrent(),
			feedApplied: (data) => this.#saveSnapshot(data),
			unauthorized: () => this.#confirmedInvalid(),
			feedFailed: () => {
				this.#sessionValidated = false;
				this.store.setWriteAuthorized(false);
				this.#queue?.pause();
				this.#scheduleRevalidation();
			},
			connectionLost: () => this.#queue?.pause()
		});
		this.#queue = new WriteQueue(slug, this.#api, this.store, {
			retryDelays: options.retryDelays
		});
		this.#queue.pause();
		this.#live = new LiveUpdates({
			url: this.#api.eventsUrl(slug),
			host: this.store,
			checkSession: () => this.#checkSession(),
			onReconnect: () => this.#revalidateAndRefresh(),
			createEventSource: options.createEventSource,
			reconnectDelays: options.reconnectDelays,
			visibility: options.visibility,
			connectivity: options.online
		});
		this.#removeClearHint =
			this.#snapshotStore?.onClear((hint) => {
				if (this.#sameIdentity(hint.identity)) void this.#checkClearHint(hint.generation);
			}) ?? null;
		this.#removeSigninHint = onRoomSignIn((signedInSlug) => {
			if (this.#identity.kind === 'room' && signedInSlug === this.slug) {
				void this.#acceptExternalSignIn();
			}
		});
	}

	/** Ops not answered by the server yet. */
	get queuedOps() {
		return this.#queue.pending;
	}

	/** Starts saved-view preparation, access revalidation and live updates. */
	retain(): void {
		this.#users += 1;
		if (this.#users === 1) {
			void this.#initialize()
				.catch((error) => {
					this.store.reportLoadFailure(error instanceof Error ? error.message : String(error));
					this.#scheduleRevalidation();
				})
				.finally(() => {
					if (this.#users > 0 && !this.#signoutBlocked) this.#live.start();
				});
		}
	}

	/** Stops live updates when nobody uses the room. Data and pending ops stay. */
	release(): void {
		this.#users = Math.max(0, this.#users - 1);
		if (this.#users === 0) {
			this.#live.stop();
			this.#clearRevalidationTimer();
		}
	}

	// Room

	renameRoom(name: string): Promise<ActionResult> {
		return this.#run({ type: 'room.rename', name });
	}

	/** Changes the password without ever storing it for retries. */
	async changePassword(currentPassword: string, newPassword: string): Promise<ActionResult<Room>> {
		if (!this.store.canWrite) return READ_ONLY;
		const change = this.#api.changePassword(this.slug, currentPassword, newPassword);
		this.#passwordChange = change.catch(() => undefined);
		try {
			const room = await change;
			await this.#revalidateAndRefresh();
			return { ok: true, result: room };
		} catch (error) {
			this.#handleUnauthorizedError(error);
			return failed(error);
		} finally {
			this.#passwordChange = null;
		}
	}

	/** Deletes the room with all its lists and items, then forgets it here. */
	async deleteRoom(password: string): Promise<ActionResult> {
		if (!this.store.canWrite) return READ_ONLY;
		try {
			await this.#api.deleteRoom(this.slug, password);
		} catch (error) {
			this.#handleUnauthorizedError(error);
			return failed(error);
		}
		this.#blockAndClear('loading', true);
		this.#queue.dispose(new ApiError(404, 'room_deleted', 'This room was deleted.'));
		if (rooms.get(this.slug) === this) rooms.delete(this.slug);
		this.#removeClearHint?.();
		this.#removeSigninHint();
		return { ok: true, result: {} };
	}

	// Share links

	/** Reads the list's current share token; it is not cached across reset operations. */
	shareLink(list: ListRef): Promise<ActionResult<ShareLink>> {
		return this.#call(() => this.#api.shareLink(this.slug, list.uid));
	}

	/** Gives the list a new share link; the old one stops working for everyone. */
	resetShareLink(list: ListRef): Promise<ActionResult<ShareLink>> {
		if (!this.store.canWrite) return Promise.resolve(READ_ONLY);
		return this.#call(() => this.#api.resetShareLink(this.slug, list.uid), true);
	}

	// Lists

	createList(name: string): Promise<ActionResult<ListCreateResult>> {
		return this.#run({ type: 'list.create', name, uid: newId() });
	}

	renameList(list: Pick<List, 'uid' | 'changed_seq'>, name: string): Promise<ActionResult> {
		return this.#run({ type: 'list.rename', list_uid: list.uid, name, base_seq: list.changed_seq });
	}

	deleteList(list: ListRef): Promise<ActionResult> {
		return this.#run({ type: 'list.delete', list_uid: list.uid });
	}

	addListTag(list: ListRef, tag: string): Promise<ActionResult> {
		return this.#run({ type: 'list.tag_add', list_uid: list.uid, tag });
	}

	removeListTag(list: ListRef, tag: string): Promise<ActionResult> {
		return this.#run({ type: 'list.tag_remove', list_uid: list.uid, tag });
	}

	/** Sends only the changed hide-done fields. */
	setVisibility(list: ListRef, changes: Partial<HideDone>): Promise<ActionResult> {
		return this.#run({ type: 'list.visibility', list_uid: list.uid, ...changes });
	}

	// Items

	/** Add-or-restore: outcome is `added` or `restored` for a checked item. */
	addItem(list: ListRef, name: string): Promise<ActionResult<ItemAddResult>> {
		return this.#run({ type: 'item.add', list_uid: list.uid, name, uid: newId() });
	}

	setDone(item: ItemRef, done: boolean): Promise<ActionResult> {
		return this.#run({ type: 'item.set_done', ...itemKeys(item), done });
	}

	changeQuantity(item: ItemRef, delta: number): Promise<ActionResult> {
		return this.#run({ type: 'item.quantity_delta', ...itemKeys(item), delta });
	}

	editItem(
		item: ItemRef & Pick<Item, 'changed_seq'>,
		changes: { name: string; description: string; quantity?: number | null }
	): Promise<ActionResult> {
		return this.#run({
			type: 'item.edit',
			...itemKeys(item),
			...changes,
			base_seq: item.changed_seq
		});
	}

	toggleItemTag(item: ItemRef, tag: string): Promise<ActionResult> {
		return this.#run({ type: 'item.toggle_tag', ...itemKeys(item), tag });
	}

	/** Deletes an item and keeps its data so `restoreItem(item.uid)` can undo it. */
	deleteItem(item: Item): Promise<ActionResult> {
		if (!this.store.canWrite) return Promise.resolve(READ_ONLY);
		this.#deleted.set(item.uid, this.store.item(item.uid) ?? item);
		return this.#run({ type: 'item.delete', ...itemKeys(item) });
	}

	/** Undo of `deleteItem`: a new item (new uid) with the kept data. */
	async restoreItem(itemUid: string): Promise<ActionResult<ItemRestoreResult>> {
		if (!this.store.canWrite) return READ_ONLY;
		const item = this.#deleted.get(itemUid);
		if (!item) {
			return { ok: false, code: 'undo_unavailable', message: 'There is nothing to undo.' };
		}
		const result = await this.#run<ItemRestoreResult>({
			type: 'item.restore',
			list_uid: item.list_uid,
			uid: newId(),
			name: item.name,
			done: item.done,
			tags: item.tags,
			description: item.description,
			quantity: item.quantity,
			completed_at: item.completed_at
		});
		if (result.ok) this.#deleted.delete(itemUid);
		return result;
	}

	// Session

	/** Signs in after any pending server sign-out and a full access/feed refresh. */
	async login(password: string): Promise<ActionResult<Room>> {
		this.#clearRevalidationTimer();
		this.#queue.pause();
		this.store.setWriteAuthorized(false);
		const loginEpoch = this.#identityEpoch;
		const transition = async () => {
			if (this.#identity.kind === 'share') {
				return { ok: false as const, code: 'read_only', message: 'A share link cannot sign in.' };
			}
			if (!(await this.#finishPendingLogout(this.#api))) {
				return {
					ok: false as const,
					code: this.#transitionError ? 'session_transition_unavailable' : 'logout_pending',
					message: this.#transitionError ?? SIGNIN_LOCK_UNAVAILABLE
				};
			}
			if (loginEpoch !== this.#identityEpoch) return this.#signoutDuringSignin();
			let signinGeneration: SnapshotGeneration | null = null;
			let signoutMarkerCleared = false;
			if (this.#snapshotStore) {
				const cleared = await this.#snapshotStore.clearSignOutAfterSignIn(this.#roomIdentity());
				signoutMarkerCleared = cleared.ok;
				if (!cleared.ok) this.#warnSnapshot();
				const current = await this.#snapshotStore.generation(this.#identity);
				if (!current.ok && current.reason === 'signed_out') {
					await this.#restoreNewerSignOut();
					return this.#signoutDuringSignin();
				}
				if (current.ok) signinGeneration = current.value;
				else this.#warnSnapshot();
			}
			let room: Room;
			try {
				room = await this.#api.login(this.slug, password);
			} catch (error) {
				this.#handleUnauthorizedError(error);
				return failed(error);
			}
			if (loginEpoch !== this.#identityEpoch) {
				await this.#restoreNewerSignOut();
				return this.#signoutDuringSignin();
			}
			if (this.#snapshotStore) {
				let pending;
				try {
					pending = await this.#snapshotStore.pendingServerLogouts();
				} catch {
					await this.#abortUnreadableSignin();
					return {
						ok: false as const,
						code: 'session_transition_unavailable',
						message: SIGNIN_STATE_UNAVAILABLE
					};
				}
				if (!pending.ok) {
					await this.#abortUnreadableSignin();
					return {
						ok: false as const,
						code: 'session_transition_unavailable',
						message: SIGNIN_STATE_UNAVAILABLE
					};
				}
				if (pending.value.some((identity) => identity.slug === this.slug)) {
					await this.#restoreNewerSignOut();
					return this.#signoutDuringSignin();
				}
				const current = await this.#snapshotStore.generation(this.#identity);
				if (!current.ok && current.reason === 'signed_out') {
					await this.#restoreNewerSignOut();
					return this.#signoutDuringSignin();
				}
				if (
					signinGeneration &&
					current.ok &&
					!this.#sameGeneration(current.value, signinGeneration)
				) {
					await this.#restoreNewerSignOut();
					return this.#signoutDuringSignin();
				}
				if (current.ok) {
					this.#snapshotGeneration = current.value;
					this.#volatileAuthorized = !signoutMarkerCleared;
				} else {
					this.#snapshotGeneration = null;
					this.#warnSnapshot();
					this.#volatileAuthorized = true;
				}
			}
			this.#signoutBlocked = false;
			const refreshed = await this.#validateAndRefresh(loginEpoch);
			if (!refreshed) {
				if (loginEpoch !== this.#identityEpoch || this.#signoutBlocked) {
					return this.#signoutDuringSignin();
				}
				return {
					ok: false as const,
					code: 'session_refresh_failed',
					message: SIGNIN_REFRESH_FAILED
				};
			}
			announceRoomSignIn(this.slug);
			return { ok: true as const, result: room };
		};

		try {
			const locked = await withRoomSessionLock(this.slug, transition, this.#locks);
			if (locked.acquired) return locked.value!;
			if (await this.#hasPendingLogout()) {
				this.store.setSnapshotWarning(SIGNIN_LOCK_UNAVAILABLE);
				return { ok: false as const, code: 'logout_pending', message: SIGNIN_LOCK_UNAVAILABLE };
			}
			// Ordinary first sign-in remains usable without Web Locks. The durable
			// marker is rechecked before and after the request; pending logout fails closed.
			return await transition();
		} catch (error) {
			this.store.reportLoadFailure(error instanceof Error ? error.message : String(error));
			return failed(error);
		}
	}

	/** Starts local sign-out immediately, then attempts only the server logout. */
	async logout(client: Pick<Api, 'logout'> = this.#api): Promise<ActionResult> {
		const hadPending = this.#queue.pending.length > 0;
		this.#blockAndClear('auth_required', false);
		if (hadPending) this.store.notify('logout_pending', PENDING_OPERATION_NOTICE);
		let marked = false;
		if (this.#snapshotStore && this.#identity.kind === 'room') {
			this.#localSignoutInProgress = true;
			try {
				const result = await this.#snapshotStore.localSignOut(this.#roomIdentity());
				marked = result.ok;
				if (result.ok) this.#snapshotGeneration = null;
				else this.#warnSnapshot();
			} catch {
				this.#warnSnapshot();
			} finally {
				this.#localSignoutInProgress = false;
			}
		}
		if (!marked) {
			this.store.setSnapshotWarning(LOGOUT_LOCAL_CLEAR_UNCONFIRMED);
			return {
				ok: false,
				code: 'local_clear_unconfirmed',
				message: LOGOUT_LOCAL_CLEAR_UNCONFIRMED
			};
		}
		if (!this.#locks) {
			this.store.setSnapshotWarning(LOGOUT_SERVER_PENDING);
			return { ok: false, code: 'server_logout_pending', message: LOGOUT_SERVER_PENDING };
		}
		let serverSignedOut = false;
		try {
			const locked = await withRoomSessionLock(
				this.slug,
				async () => {
					const pending = await this.#snapshotStore!.pendingServerLogouts();
					if (!pending.ok || !pending.value.some((identity) => identity.slug === this.slug))
						return false;
					const generation = await this.#snapshotStore!.generation(this.#identity);
					if (generation.ok || generation.reason !== 'signed_out') return false;
					await client.logout(this.slug);
					serverSignedOut = true;
					const acknowledged = await this.#snapshotStore!.acknowledgeServerLogout(
						this.#roomIdentity()
					);
					return acknowledged.ok;
				},
				this.#locks
			);
			if (locked.acquired && locked.value) return { ok: true, result: {} };
			const code = serverSignedOut ? 'logout_marker_unacknowledged' : 'server_logout_pending';
			const message = serverSignedOut ? LOGOUT_MARKER_UNACKNOWLEDGED : LOGOUT_SERVER_PENDING;
			this.store.setSnapshotWarning(message);
			return { ok: false, code, message };
		} catch (error) {
			return serverSignedOut
				? { ok: false, code: 'logout_marker_unacknowledged', message: LOGOUT_MARKER_UNACKNOWLEDGED }
				: failed(error);
		}
	}

	/** Synchronous local-only hook retained for callers that only need to clear UI. */
	signedOut(): void {
		this.#blockAndClear('auth_required', false);
		if (this.#identity.kind === 'room' && this.#snapshotStore) {
			void this.#snapshotStore.localSignOut(this.#roomIdentity()).then((result) => {
				if (!result.ok) this.#warnSnapshot();
			});
		}
	}

	#sameIdentity(identity: SnapshotIdentity): boolean {
		return (
			identity.kind === this.#identity.kind &&
			(identity.kind === 'room'
				? identity.slug === (this.#identity as RoomIdentity).slug
				: identity.token === (this.#identity as { kind: 'share'; token: string }).token)
		);
	}

	#roomIdentity(): RoomIdentity {
		return { kind: 'room', slug: this.slug };
	}

	async #initialize(): Promise<void> {
		const startEpoch = this.#identityEpoch;
		if (this.#snapshotStore) {
			const generation = await this.#snapshotStore.generation(this.#identity);
			if (generation.ok) {
				this.#snapshotGeneration = generation.value;
			} else if (generation.reason === 'signed_out' && !this.#volatileAuthorized) {
				this.#signoutBlocked = true;
				this.store.clear('auth_required');
				if (this.#identity.kind === 'room') {
					const retried = await this.#retryPendingLogout();
					if (!retried) this.store.setSnapshotWarning(SIGNIN_LOCK_UNAVAILABLE);
				}
				return;
			} else {
				this.#warnSnapshot();
			}
			if (this.#hydrateSavedView && this.#snapshotGeneration) {
				const saved = await this.#snapshotStore.read(this.#identity);
				const current = await this.#snapshotStore.generation(this.#identity);
				if (
					saved.ok &&
					saved.value &&
					current.ok &&
					this.#sameGeneration(current.value, this.#snapshotGeneration) &&
					startEpoch === this.#identityEpoch
				) {
					this.store.hydrate(saved.value);
				} else if (!saved.ok) {
					this.#warnSnapshot();
				}
			}
		}
		await this.#revalidateAndRefresh();
	}

	async #retryPendingLogout(): Promise<boolean> {
		if (!this.#snapshotStore || this.#identity.kind !== 'room') return false;
		let pending;
		try {
			pending = await this.#snapshotStore.pendingServerLogouts();
		} catch {
			this.#warnSnapshot();
			return false;
		}
		if (!pending.ok) {
			this.#warnSnapshot();
			return false;
		}
		if (!pending.value.some((identity) => identity.slug === this.slug)) return false;
		const retry = async () => {
			const latest = await this.#snapshotStore!.pendingServerLogouts();
			if (!latest.ok) return false;
			if (!latest.value.some((identity) => identity.slug === this.slug)) return true;
			try {
				await this.#api.logout(this.slug);
				const acknowledged = await this.#snapshotStore!.acknowledgeServerLogout(
					this.#roomIdentity()
				);
				if (!acknowledged.ok) this.#warnSnapshot();
				return acknowledged.ok;
			} catch {
				return false;
			}
		};
		try {
			const locked = await withRoomSessionLock(this.slug, retry, this.#locks);
			if (!locked.acquired) return false;
			return locked.value ?? false;
		} catch {
			return false;
		}
	}

	async #finishPendingLogout(client: Pick<Api, 'logout'>): Promise<boolean> {
		this.#transitionError = null;
		if (!this.#snapshotStore || this.#identity.kind !== 'room') return true;
		let pending;
		try {
			pending = await this.#snapshotStore.pendingServerLogouts();
		} catch {
			this.#warnSnapshot();
			this.#transitionError = SIGNIN_STATE_UNAVAILABLE;
			return false;
		}
		if (!pending.ok) {
			this.#warnSnapshot();
			this.#transitionError = SIGNIN_STATE_UNAVAILABLE;
			return false;
		}
		if (!pending.value.some((identity) => identity.slug === this.slug)) return true;
		if (!this.#locks) return false;
		try {
			await client.logout(this.slug);
			const acknowledged = await this.#snapshotStore.acknowledgeServerLogout(this.#roomIdentity());
			return acknowledged.ok;
		} catch {
			return false;
		}
	}

	async #revalidateAndRefresh(): Promise<boolean> {
		if (this.#signoutBlocked) return false;
		this.#clearRevalidationTimer();
		const epoch = this.#identityEpoch;
		this.store.setWriteAuthorized(false);
		this.#queue.pause();
		const validate = () => this.#validateAndRefresh(epoch);
		try {
			const locked = await withRoomSessionLock(this.slug, validate, this.#locks);
			if (locked.acquired) return locked.value ?? false;
			if (await this.#hasPendingLogout()) return false;
			return await validate();
		} catch (error) {
			this.#sessionValidated = false;
			this.store.reportLoadFailure(error instanceof Error ? error.message : String(error));
			this.#scheduleRevalidation();
			return false;
		}
	}

	async #validateAndRefresh(epoch: number): Promise<boolean> {
		if (epoch !== this.#identityEpoch || this.#signoutBlocked) return false;
		if (!(await this.#identityStillCurrent())) return false;
		if (!this.#isShare) {
			try {
				await this.#api.whoAmI(this.slug);
			} catch (error) {
				this.#handleUnauthorizedError(error);
				this.#sessionValidated = false;
				if (!(error instanceof ApiError && error.status === 401)) {
					this.store.reportLoadFailure(error instanceof Error ? error.message : String(error));
					this.#scheduleRevalidation();
				}
				return false;
			}
		}
		if (epoch !== this.#identityEpoch || this.#signoutBlocked) return false;
		this.#sessionValidated = true;
		const refreshed = await this.store.refresh();
		if (!refreshed || epoch !== this.#identityEpoch || this.#signoutBlocked) return false;
		if (!(await this.#identityStillCurrent())) return false;
		this.#sessionValidated = true;
		this.store.setWriteAuthorized(true);
		this.#revalidationAttempt = 0;
		this.store.syncQueued(this.#queue.pending.length);
		this.#queue.resume();
		if (this.#users > 0) this.#live.start();
		return true;
	}

	#scheduleRevalidation(): void {
		if (this.#signoutBlocked || this.#users === 0 || this.#revalidationTimer !== null) return;
		const delay =
			RECONNECT_DELAYS[Math.min(this.#revalidationAttempt, RECONNECT_DELAYS.length - 1)];
		this.#revalidationAttempt += 1;
		this.#revalidationTimer = setTimeout(() => {
			this.#revalidationTimer = null;
			void this.#revalidateAndRefresh().then((refreshed) => {
				if (!refreshed) this.#scheduleRevalidation();
			});
		}, delay);
	}

	#clearRevalidationTimer(): void {
		if (this.#revalidationTimer !== null) clearTimeout(this.#revalidationTimer);
		this.#revalidationTimer = null;
	}

	async #identityStillCurrent(): Promise<boolean> {
		if (this.#signoutBlocked) return false;
		if (!this.#snapshotStore) return true;
		try {
			const current = await this.#snapshotStore.generation(this.#identity);
			if (!current.ok) {
				if (current.reason === 'signed_out') {
					this.#blockAndClear('auth_required', false);
					return false;
				}
				this.#warnSnapshot();
				return true;
			}
			if (!this.#snapshotGeneration) {
				this.#snapshotGeneration = current.value;
				return true;
			}
			if (!this.#sameGeneration(current.value, this.#snapshotGeneration)) {
				this.#blockAndClear('auth_required', false);
				return false;
			}
			return true;
		} catch {
			this.#warnSnapshot();
			return true;
		}
	}

	async #saveSnapshot(data: SnapshotData): Promise<void> {
		if (
			!this.#snapshotStore ||
			!this.#sessionValidated ||
			!this.#snapshotGeneration ||
			this.#signoutBlocked ||
			this.#volatileAuthorized
		)
			return;
		const epoch = this.#identityEpoch;
		if (!(await this.#identityStillCurrent()) || epoch !== this.#identityEpoch) return;
		try {
			const saved = await this.#snapshotStore.save(this.#identity, data, this.#snapshotGeneration);
			if (saved.ok) {
				if (epoch === this.#identityEpoch && !this.#signoutBlocked) {
					this.store.savedAt = saved.value.savedAt;
					this.store.setSnapshotWarning(null);
				}
			} else if (saved.reason === 'stale' || saved.reason === 'signed_out') {
				this.#blockAndClear('auth_required', false);
			} else {
				this.#warnSnapshot();
			}
		} catch {
			this.#warnSnapshot();
		}
	}

	async #checkClearHint(hintGeneration: number): Promise<void> {
		if (!this.#snapshotStore) return;
		const current = await this.#snapshotStore.generation(this.#identity);
		// A hint may arrive after a newer sign-in. Only the durable current
		// generation (or a signed-out marker) may revoke the visible view.
		if (current.ok) {
			if (
				current.value.generation !== hintGeneration ||
				(this.#snapshotGeneration && this.#sameGeneration(current.value, this.#snapshotGeneration))
			)
				return;
		} else if (current.reason !== 'signed_out') {
			this.#warnSnapshot();
			return;
		}
		this.#blockAndClear('auth_required', false);
		if (!this.#localSignoutInProgress) void this.#handleClearHint();
	}

	async #handleClearHint(): Promise<void> {
		if (!this.#snapshotStore || this.#identity.kind !== 'room') return;
		try {
			const pending = await this.#snapshotStore.pendingServerLogouts();
			if (pending.ok && pending.value.some((identity) => identity.slug === this.slug)) {
				void this.#retryPendingLogout();
			}
		} catch {
			this.#warnSnapshot();
		}
	}

	async #acceptExternalSignIn(): Promise<void> {
		if (this.#identity.kind !== 'room' || !this.#signoutBlocked) return;
		try {
			const current = await this.#snapshotStore?.generation(this.#identity);
			if (current && !current.ok) return;
			this.#snapshotGeneration = current?.ok ? current.value : null;
			this.#signoutBlocked = false;
			await this.#revalidateAndRefresh();
		} catch {
			this.#warnSnapshot();
		}
	}

	async #checkSession(): Promise<SessionState> {
		if (this.#passwordChange) await this.#passwordChange;
		if (this.#signoutBlocked || (await this.#hasPendingLogout())) return 'signed_out';
		const check = async (): Promise<SessionState> => {
			if (!(await this.#identityStillCurrent())) return 'signed_out';
			if (this.#isShare) {
				try {
					await this.#api.whoAmI(this.slug);
					return 'signed_in';
				} catch (error) {
					return error instanceof ApiError && error.status === 401 ? 'signed_out' : 'unknown';
				}
			}
			try {
				await this.#api.whoAmI(this.slug);
				return 'signed_in';
			} catch (error) {
				return error instanceof ApiError && error.status === 401 ? 'signed_out' : 'unknown';
			}
		};
		try {
			const locked = await withRoomSessionLock(this.slug, check, this.#locks);
			return locked.acquired ? locked.value! : check();
		} catch {
			return 'unknown';
		}
	}

	async #hasPendingLogout(): Promise<boolean> {
		if (!this.#snapshotStore || this.#identity.kind !== 'room') return false;
		try {
			const pending = await this.#snapshotStore.pendingServerLogouts();
			if (!pending.ok) {
				this.#warnSnapshot();
				return false;
			}
			return pending.value.some((identity) => identity.slug === this.slug);
		} catch {
			this.#warnSnapshot();
			return false;
		}
	}

	#handleUnauthorizedError(error: unknown): void {
		if (error instanceof ApiError && error.status === 401) this.#confirmedInvalid();
	}

	#confirmedInvalid(): void {
		this.#blockAndClear('auth_required', true);
	}

	#blockAndClear(status: RoomStatus, persist: boolean): void {
		this.#identityEpoch += 1;
		this.#clearRevalidationTimer();
		this.#sessionValidated = false;
		this.#signoutBlocked = true;
		this.#volatileAuthorized = false;
		this.store.setWriteAuthorized(false);
		this.#queue.pause();
		this.#live?.stop();
		this.#deleted.clear();
		this.store.clear(status);
		if (persist && this.#snapshotStore) {
			void this.#snapshotStore.clear(this.#identity).then((result) => {
				if (!result.ok) this.#warnSnapshot();
			});
		}
	}

	async #restoreNewerSignOut(): Promise<void> {
		if (this.#snapshotStore && this.#identity.kind === 'room') {
			const restored = await this.#snapshotStore.localSignOut(this.#roomIdentity());
			if (!restored.ok) this.#warnSnapshot();
		}
	}

	async #abortUnreadableSignin(): Promise<void> {
		this.#blockAndClear('auth_required', false);
		try {
			const marked = await this.#snapshotStore?.localSignOut(this.#roomIdentity());
			if (marked && !marked.ok) this.#warnSnapshot();
		} catch {
			this.#warnSnapshot();
		}
		try {
			await this.#api.logout(this.slug);
		} catch {
			// Local access stays blocked even if the best-effort server logout fails.
		}
	}

	#signoutDuringSignin(): ActionResult<Room> {
		this.#blockAndClear('auth_required', false);
		return { ok: false, code: 'signed_out', message: 'Room sign-in was interrupted by sign-out.' };
	}

	#warnSnapshot(): void {
		this.store.setSnapshotWarning(SNAPSHOT_UNAVAILABLE);
	}

	#sameGeneration(a: SnapshotGeneration, b: SnapshotGeneration): boolean {
		return a.identityKey === b.identityKey && a.generation === b.generation;
	}

	async #run<R = Record<string, never>>(op: Op): Promise<ActionResult<R>> {
		if (!this.store.canWrite) return READ_ONLY;
		const epoch = this.#identityEpoch;
		try {
			const response = await this.#queue.send(op);
			if (epoch !== this.#identityEpoch && (response.status === 'rejected' || !this.store.canWrite))
				return this.#clearedAction();
			if (response.status === 'rejected') {
				return { ok: false, code: response.code, message: response.message };
			}
			if (this.store.canWrite) await this.store.catchUp(response.seq);
			return { ok: true, result: response.result as R };
		} catch (error) {
			if (epoch !== this.#identityEpoch) return this.#clearedAction();
			this.#handleUnauthorizedError(error);
			return failed(error);
		}
	}

	#clearedAction(): { ok: false; code: string; message: string } {
		return {
			ok: false,
			code: 'session_changed',
			message: 'Room access changed. Check the room before retrying.'
		};
	}

	async #call<R>(request: () => Promise<R>, roomMemberReset = false): Promise<ActionResult<R>> {
		try {
			return { ok: true, result: await request() };
		} catch (error) {
			if (
				roomMemberReset &&
				this.#api instanceof ShareApi &&
				error instanceof ApiError &&
				error.status === 401 &&
				error.code === 'not_authenticated'
			) {
				this.#api.forgetMemberRoom(this.slug);
				this.store.dropMemberRoom();
				void this.#revalidateAndRefresh();
			} else this.#handleUnauthorizedError(error);
			return failed(error);
		}
	}
}

function itemKeys(item: ItemRef) {
	return { list_uid: item.list_uid, item_uid: item.uid };
}

// The open rooms of this page. Handles survive route changes so pending ops keep their ids.
const rooms = new Map<string, RoomHandle>();

/** Opens a room (or reuses the open one): loads data and starts live updates. */
export function openRoom(slug: string, options?: RoomOptions): RoomHandle {
	let room = rooms.get(slug);
	if (!room) {
		room = new RoomHandle(slug, options);
		rooms.set(slug, room);
	}
	room.retain();
	return room;
}

/** Stops live updates for one `openRoom` call. */
export function closeRoom(room: RoomHandle): void {
	room.release();
}

const shares = new Map<string, RoomHandle>();

/** Opens a share link (or reuses it): loads its view and starts live updates. */
export function openShare(token: string, options: RoomOptions = {}): RoomHandle {
	let share = shares.get(token);
	if (!share) {
		share = new RoomHandle(token, {
			...options,
			api: new ShareApi(options.shareApi ?? defaultApi)
		});
		shares.set(token, share);
	}
	share.retain();
	return share;
}

/** Stops live updates for one `openShare` call. */
export function closeShare(share: RoomHandle): void {
	share.release();
}

async function standaloneLogin(
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
		if (pending.ok && pending.value.some((identity) => identity.slug === slug)) {
			return { ok: false, code: 'logout_pending', message: SIGNIN_LOCK_UNAVAILABLE };
		}
		return await signIn();
	} catch (error) {
		return failed(error);
	}
}

/** Signs in to a room and validates its fresh server feed before enabling writes. */
export async function login(
	slug: string,
	password: string,
	client: Api = defaultApi
): Promise<ActionResult<Room>> {
	const room = rooms.get(slug);
	if (room) return room.login(password);
	return standaloneLogin(slug, password, client);
}

/** Clears local room access first, then attempts the server sign-out. */
export async function logout(slug: string, client: Api = defaultApi): Promise<ActionResult> {
	const room = rooms.get(slug);
	if (room) return room.logout(client);
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
				if (!pending.ok || !pending.value.some((entry) => entry.slug === slug)) return false;
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
	} catch (error) {
		return serverSignedOut
			? { ok: false, code: 'logout_marker_unacknowledged', message: LOGOUT_MARKER_UNACKNOWLEDGED }
			: failed(error);
	}
}

/** The room if signed in, null if not. Throws for network or server errors. */
export async function whoAmI(slug: string, client: Api = defaultApi): Promise<Room | null> {
	try {
		return await client.whoAmI(slug);
	} catch (error) {
		if (error instanceof ApiError && error.status === 401) return null;
		throw error;
	}
}

/** The server's last-room hint is routing only, never authorization. */
/** The last-room hint is for routing only; it never authorizes access. */
export function lastRoom(client: Api = defaultApi): Promise<string | null> {
	return client.lastRoom();
}
