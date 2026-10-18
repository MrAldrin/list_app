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
import { compat, INCOMPATIBLE_CODE, INCOMPATIBLE_MESSAGE } from './compat.svelte';
import { BACKOFF_DELAYS, backoffDelay } from './backoff';
import { LiveUpdates, type EventSourceFactory, type SessionState } from './events';
import { newId } from './ids';
import {
	SIGNIN_LOCK_UNAVAILABLE,
	SIGNIN_REFRESH_FAILED,
	SNAPSHOT_UNAVAILABLE,
	LOGOUT_LOCAL_CLEAR_UNCONFIRMED,
	PENDING_OPERATION_NOTICE
} from './messages';
import {
	finishServerSignOut,
	hasPendingServerLogout,
	retryPendingServerLogout
} from './pending-logout';
import { failed, type ActionResult } from './result';
import { itemName } from './overlay';
import { rowOf } from './rebase';
import { createRoomStore, RoomStore, type RoomStatus } from './room-store.svelte';
import { signInRoom, SIGNIN_INTERRUPTED } from './room-signin';
import { ShareApi } from './share';
import {
	browserSessionLocks,
	onRoomSignIn,
	withRoomSessionLock,
	type SessionLockManager
} from './session-transition';
import {
	browserSnapshots,
	standaloneLogin,
	standaloneLogout,
	takeVolatileSignIn
} from './standalone-session';
import {
	type RoomIdentity,
	type SnapshotData,
	type SnapshotGeneration,
	type SnapshotIdentity,
	type SnapshotStore
} from './snapshot-store';
import { ApiError, NetworkError } from './types';
import type {
	HideDone,
	Item,
	ItemAddResult,
	ItemRestoreResult,
	List,
	ListCreateResult,
	Op,
	Room,
	SentOp,
	ShareLink
} from './types';
import type { HeldOp, UnreadableOp } from './queue-entries';
import { createQueueStorage, type QueueStorage } from './queue-storage';
import { QueueView } from './queue-view.svelte';
import { WriteQueue } from './write-queue';

export * from './types';
export type { ActionResult } from './result';
export * as admin from './admin';
export * as invitation from './invitation';
export type { RoomStatus, Notice } from './room-store.svelte';
export type { LiveState } from './events';
export {
	connectionStatus,
	CONNECTION_STATUS_DELAY,
	offlineNoticeText,
	SAVED_VIEW_NOTICE_DELAY,
	savedTimeLabel,
	waitingChangesText,
	type ConnectionStatus
} from './status';
export { RoomStore } from './room-store.svelte';
export {
	filterVisibleItems,
	countHiddenChecked,
	DEFAULT_HIDE_DONE,
	MAX_HIDE_DONE_COUNT
} from './visibility';
export {
	ITEM_SORTS,
	itemSortChoice,
	sortItems,
	sortLists,
	sortTags,
	type ItemSort,
	type ItemSortChoice,
	type ItemSortKey
} from './order';
export {
	cantBeSentText,
	describeChange,
	notSavedCountText,
	notSentYetText,
	willBeDiscardedText
} from './not-saved';
export type { NotSavedChange } from './room-store.svelte';
export { newId } from './ids';

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
	/** Where queued ops are kept. Default: IndexedDB when available, else memory. */
	queueStorage?: QueueStorage;
}

const READ_ONLY = {
	ok: false as const,
	code: 'read_only',
	message: 'Saved data is read-only until room access is refreshed.'
};
const INCOMPATIBLE = {
	ok: false as const,
	code: INCOMPATIBLE_CODE,
	message: INCOMPATIBLE_MESSAGE
};

/** One room or one share link: committed data, queue, and live updates. */
/** How long logout waits for the sign-out marker before it clears the view anyway. */
export const LOCAL_SIGNOUT_TIMEOUT_MS = 5_000;
const TIMED_OUT = Symbol('timed out');

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | typeof TIMED_OUT> {
	let timer: ReturnType<typeof setTimeout> | undefined;
	const timeout = new Promise<typeof TIMED_OUT>((resolve) => {
		timer = setTimeout(() => resolve(TIMED_OUT), ms);
	});
	// A rejection after the timeout must not become an unhandled rejection.
	promise.catch(() => undefined);
	try {
		return await Promise.race([promise, timeout]);
	} finally {
		clearTimeout(timer);
	}
}

export class RoomHandle {
	readonly slug: string;
	readonly store: RoomStore;
	readonly #api: RoomApi;
	readonly #queue: WriteQueue;
	readonly #queueStorage: QueueStorage;
	readonly #queueKey: string;
	readonly #queueView = new QueueView();
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
	#loggingOut = false;
	#revalidationAttempt = 0;
	#revalidationTimer: ReturnType<typeof setTimeout> | null = null;
	#notSavedWrites: Promise<void> = Promise.resolve();

	constructor(slug: string, options: RoomOptions = {}) {
		this.slug = slug;
		this.#api = options.api ?? defaultApi;
		this.#isShare = this.#api instanceof ShareApi;
		this.#identity = this.#isShare ? { kind: 'share', token: slug } : { kind: 'room', slug };
		if (this.#identity.kind === 'room') {
			this.#volatileAuthorized = takeVolatileSignIn(slug);
		}
		this.#snapshotStore =
			options.snapshotStore === undefined ? browserSnapshots() : options.snapshotStore;
		this.#locks = options.sessionLocks === undefined ? browserSessionLocks() : options.sessionLocks;
		this.#hydrateSavedView = options.hydrateSavedView ?? false;
		this.#queueKey = this.#isShare ? `share:${slug}` : `room:${slug}`;
		this.#queueStorage = options.queueStorage ?? createQueueStorage(this.#queueKey);
		this.store = createRoomStore(slug, this.#api, {
			beforeApply: () => this.#identityStillCurrent(),
			deferClear: () => this.#localSignoutInProgress,
			feedApplied: (data) => this.#saveSnapshot(data),
			unauthorized: () => this.#confirmedInvalid(),
			feedFailed: () => {
				this.#sessionValidated = false;
				this.store.setWriteAuthorized(false);
				this.#queue?.pause();
				this.#scheduleRevalidation();
			},
			connectionLost: () => this.#queue?.pause(),
			persistNotSaved: (change, removedKeys, add) => {
				const write = this.#notSavedWrites.then(() =>
					change
						? add
							? this.#queueStorage.addNotSaved(change)
							: this.#queueStorage.updateNotSaved(change)
						: this.#queueStorage.removeNotSaved(removedKeys)
				);
				this.#notSavedWrites = write.catch(() => undefined);
			}
		});
		this.#queue = new WriteQueue(slug, this.#api, this.store, {
			retryDelays: options.retryDelays,
			key: this.#queueKey,
			locks: this.#locks,
			storage: this.#queueStorage,
			onChange: (snapshot) => this.#queueView.apply(snapshot)
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

	/** Why a write cannot start now, or null when it may. A new server version wins. */
	#guardWrite(): typeof READ_ONLY | typeof INCOMPATIBLE | null {
		if (compat.incompatible) return INCOMPATIBLE;
		return this.store.canWrite ? null : READ_ONLY;
	}

	/**
	 * Why an edit cannot start now, or null when it may. Edits also start
	 * offline: they are queued (see `#run`).
	 */
	#guardEdit(): typeof READ_ONLY | typeof INCOMPATIBLE | null {
		if (compat.incompatible) return INCOMPATIBLE;
		return this.store.canEdit ? null : READ_ONLY;
	}

	/** Ops not answered by the server yet. */
	get queuedOps() {
		return this.#queue.pending;
	}

	/** Ops waiting on this device, held and unreadable ones included. */
	get waitingCount(): number {
		return this.#queueView.waiting;
	}

	/** Ops older than 30 days: sent only when the user chooses. */
	get heldOps(): readonly HeldOp[] {
		return this.#queueView.held;
	}

	/** Ops waiting for an explicit send choice after sign-out. */
	get signoutHeldOps(): readonly HeldOp[] {
		return this.#queueView.signoutHeld;
	}

	/** Ops this app cannot read or send (for example, written by a newer version). */
	get unreadableOps(): readonly UnreadableOp[] {
		return this.#queueView.unreadable;
	}

	/** False when waiting changes live in memory only (no IndexedDB). */
	get changesDurable(): boolean {
		return this.#queueView.durable;
	}

	/** Sends the held ops now, in their usual order. */
	sendHeld(): void {
		this.#queue.sendHeld();
	}

	/** Sends recent sign-out-held ops after the user explicitly chooses. */
	sendAfterSignIn(): void {
		this.#queue.sendAfterSignIn();
	}

	/** Drops one waiting op. False when it is being sent right now. */
	discard(opId: string): boolean {
		return this.#queue.discard(opId);
	}

	/** Drops every waiting op that is not being sent right now (R9: access gone). */
	discardWaiting(): void {
		this.#queue.discardAll();
	}

	/** True for a share link (its ops cannot be sent once the link is reset). */
	get isShare(): boolean {
		return this.#isShare;
	}

	/**
	 * Waiting changes cannot be sent: access is gone (R9). For a room, sign in
	 * again; for a share link, only discarding helps.
	 */
	get accessLost(): boolean {
		return this.store.status === 'auth_required' && this.#queueView.waiting > 0;
	}

	/**
	 * Sends a refused change again as a new op, based on the row's current
	 * `changed_seq` (R2, "Save mine anyway"). The entry leaves the Not saved list.
	 */
	saveMineAnyway(id: number): Promise<ActionResult> {
		const blocked = this.#guardEdit();
		if (blocked) return Promise.resolve(blocked);
		const change = this.store.notSaved.find((item) => item.id === id);
		const seq = change ? this.store.knownSeq(rowOf(change.op) ?? '') : undefined;
		if (!change || seq === undefined) {
			return Promise.resolve({
				ok: false,
				code: 'unavailable',
				message: 'This change can no longer be saved.'
			});
		}
		const body: Partial<SentOp> = { ...change.op };
		delete body.op_id;
		if (change.retryOpId) {
			return Promise.resolve({
				ok: false,
				code: 'retry_pending',
				message: 'This change is already being retried.'
			});
		}
		return this.#run({ ...body, base_seq: seq } as Op, (sent) => {
			this.store.markNotSavedRetry(id, sent.op_id);
		});
	}

	/** Starts saved-view preparation, access revalidation and live updates. */
	retain(): void {
		this.#users += 1;
		if (this.#users === 1) {
			// Old snapshots of other rooms go; this room's snapshot stays.
			void this.#snapshotStore?.prune(this.#identity);
			void this.#initialize()
				.catch((error) => {
					this.store.reportLoadFailure(error);
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
		const blocked = this.#guardWrite();
		if (blocked) return blocked;
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
		const blocked = this.#guardWrite();
		if (blocked) return blocked;
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
		const blocked = this.#guardWrite();
		if (blocked) return Promise.resolve(blocked);
		return this.#call(() => this.#api.resetShareLink(this.slug, list.uid), true);
	}

	// Lists

	/** Needs a connection: the new list gets its address from the server. */
	createList(name: string): Promise<ActionResult<ListCreateResult>> {
		return this.#runOnline({ type: 'list.create', name, uid: newId() });
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

	/** `item` is the item as shown: its `changed_seq` is the state the user saw. */
	setDone(item: ItemRef & Pick<Item, 'changed_seq'>, done: boolean): Promise<ActionResult> {
		return this.#run({
			type: 'item.set_done',
			...itemKeys(item),
			done,
			base_seq: item.changed_seq
		});
	}

	changeQuantity(item: ItemRef, delta: number): Promise<ActionResult> {
		return this.#run({ type: 'item.quantity_delta', ...itemKeys(item), delta });
	}

	editItem(
		item: ItemRef & Pick<Item, 'changed_seq'>,
		changes: { name: string; description: string; quantity?: number | null; date?: string | null }
	): Promise<ActionResult> {
		return this.#run({
			type: 'item.edit',
			...itemKeys(item),
			...changes,
			base_seq: item.changed_seq
		});
	}

	/** `active` is the wanted state: the tag is off now, so the op turns it on (or back). */
	toggleItemTag(item: ItemRef & Pick<Item, 'tags'>, tag: string): Promise<ActionResult> {
		return this.#run({
			type: 'item.toggle_tag',
			...itemKeys(item),
			tag,
			active: !item.tags.includes(tag)
		});
	}

	/** Deletes an item and keeps its data so `restoreItem(item.uid)` can undo it. */
	deleteItem(item: Item): Promise<ActionResult> {
		const blocked = this.#guardEdit();
		if (blocked) return Promise.resolve(blocked);
		this.#deleted.set(item.uid, this.store.item(item.uid) ?? item);
		return this.#run({ type: 'item.delete', ...itemKeys(item) });
	}

	/** Undo of `deleteItem`: a new item (new uid) with the kept data. */
	async restoreItem(itemUid: string): Promise<ActionResult<ItemRestoreResult>> {
		const blocked = this.#guardEdit();
		if (blocked) return blocked;
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
			completed_at: item.completed_at,
			date: item.date,
			add_count: item.add_count,
			added_at: item.added_at
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
		if (this.#identity.kind === 'share') {
			return { ok: false, code: 'read_only', message: 'A share link cannot sign in.' };
		}
		const loginEpoch = this.#identityEpoch;
		return signInRoom({
			slug: this.slug,
			password,
			snapshots: this.#snapshotStore,
			client: this.#api,
			locks: this.#locks,
			warn: (message) => this.store.setSnapshotWarning(message),
			stillCurrent: () => loginEpoch === this.#identityEpoch,
			block: () => this.#blockAndClear('auth_required', false),
			onLoginError: (error) => this.#handleUnauthorizedError(error),
			complete: async ({ generation, markerCleared }) => {
				if (generation?.ok) {
					this.#snapshotGeneration = generation.value;
					this.#volatileAuthorized = !markerCleared;
				} else if (generation) {
					this.#snapshotGeneration = null;
					this.#warnSnapshot();
					this.#volatileAuthorized = true;
				}
				this.#signoutBlocked = false;
				if (await this.#validateAndRefresh(loginEpoch)) return null;
				if (loginEpoch !== this.#identityEpoch || this.#signoutBlocked) {
					this.#blockAndClear('auth_required', false);
					return { ok: false, code: 'signed_out', message: SIGNIN_INTERRUPTED };
				}
				return { ok: false, code: 'session_refresh_failed', message: SIGNIN_REFRESH_FAILED };
			},
			onError: (error) => this.store.reportLoadFailure(error)
		});
	}

	/** Starts local sign-out immediately, then attempts only the server logout. */
	async logout(client: Pick<Api, 'logout'> = this.#api): Promise<ActionResult> {
		// Our own clear hint must not start a second server sign-out that races
		// this one for the session lock and its answer.
		this.#loggingOut = true;
		try {
			return await this.#logout(client);
		} finally {
			this.#loggingOut = false;
		}
	}

	async #logout(client: Pick<Api, 'logout'>): Promise<ActionResult> {
		const hadPending = this.#queue.waiting > 0;
		// Stop writes now, but keep showing the room until the sign-out marker is
		// stored. Showing the password prompt first would let a quick reload find
		// no marker and a cookie that still works.
		this.#clearRevalidationTimer();
		this.#signoutBlocked = true;
		this.store.setWriteAuthorized(false);
		this.store.setEditable(false);
		this.#queue.pause();
		await this.#queue.holdForSignOut();
		// A live event or reconnect must not reload (and so clear) the room
		// while the marker is still being stored.
		this.#live.stop();
		let marked = false;
		if (this.#snapshotStore && this.#identity.kind === 'room') {
			this.#localSignoutInProgress = true;
			try {
				const result = await withTimeout(
					this.#snapshotStore.localSignOut(this.#roomIdentity()),
					LOCAL_SIGNOUT_TIMEOUT_MS
				);
				// A timeout is reported as unconfirmed; a late answer changes nothing.
				marked = result !== TIMED_OUT && result.ok;
				if (marked) this.#snapshotGeneration = null;
				else this.#warnSnapshot();
			} catch {
				this.#warnSnapshot();
			} finally {
				this.#localSignoutInProgress = false;
			}
		}
		this.#blockAndClear('auth_required', false);
		if (hadPending) this.store.notify('logout_pending', PENDING_OPERATION_NOTICE);
		if (!marked) {
			this.store.setSnapshotWarning(LOGOUT_LOCAL_CLEAR_UNCONFIRMED);
			return {
				ok: false,
				code: 'local_clear_unconfirmed',
				message: LOGOUT_LOCAL_CLEAR_UNCONFIRMED
			};
		}
		return finishServerSignOut({
			slug: this.slug,
			identity: this.#roomIdentity(),
			snapshots: this.#snapshotStore!,
			client,
			locks: this.#locks,
			warn: (message) => this.store.setSnapshotWarning(message)
		});
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
		// Ops stored by an earlier visit wait in the queue before anything sends.
		await this.#queue.load();
		this.store.loadNotSaved(await this.#queueStorage.readNotSaved());
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
			// Moving between pages reopens the room. Its data from the server is
			// at least as new as the saved view, so keep it.
			if (this.#hydrateSavedView && this.#snapshotGeneration && !this.store.confirmed) {
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
		return retryPendingServerLogout({
			slug: this.slug,
			identity: this.#roomIdentity(),
			snapshots: this.#snapshotStore,
			api: this.#api,
			locks: this.#locks,
			warn: () => this.#warnSnapshot()
		});
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
			this.store.reportLoadFailure(error);
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
					this.store.reportLoadFailure(error);
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
		// A clear forgets the projection of stored ops; reading them again shows
		// them (ops already shown are skipped).
		await this.#queue.load();
		this.store.syncQueued(this.#queue.waiting);
		this.#queue.resume();
		if (this.#users > 0) this.#live.start();
		return true;
	}

	#scheduleRevalidation(): void {
		if (this.#signoutBlocked || this.#users === 0 || this.#revalidationTimer !== null) return;
		const delay = backoffDelay(BACKOFF_DELAYS, this.#revalidationAttempt);
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
		if (!this.#localSignoutInProgress && !this.#loggingOut) void this.#handleClearHint();
	}

	async #handleClearHint(): Promise<void> {
		if (!this.#snapshotStore || this.#identity.kind !== 'room') return;
		try {
			const pending = await this.#snapshotStore.pendingServerLogouts();
			if (pending.ok && pending.value.some((identity) => identity.slug === this.slug)) {
				await this.#queue.holdForSignOut();
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
		return hasPendingServerLogout(this.#snapshotStore, this.slug, () => this.#warnSnapshot());
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

	#warnSnapshot(): void {
		this.store.setSnapshotWarning(SNAPSHOT_UNAVAILABLE);
	}

	#sameGeneration(a: SnapshotGeneration, b: SnapshotGeneration): boolean {
		return a.identityKey === b.identityKey && a.generation === b.generation;
	}

	/**
	 * Runs an edit. Online, it waits for the server's answer. Offline (or while
	 * access is revalidated) it is queued at once: the change shows through the
	 * overlay, the answer comes later, and a rejection is a toast then (6.3 will
	 * list it instead). Stored ops are sent on reconnect (see RoomStore).
	 */
	#run<R = Record<string, never>>(
		op: Op,
		onQueued?: (sent: SentOp) => void
	): Promise<ActionResult<R>> {
		const blocked = this.#guardEdit();
		if (blocked) return Promise.resolve(blocked);
		if (this.store.canWrite) return this.#runOnline<R>(op, onQueued);
		const provisional = this.#provisional<R>(op);
		// The answer, if it is a failure, goes to the Not saved list (the op waited);
		// nobody awaits it here.
		this.#queue.send(op, true, onQueued).catch(() => undefined);
		return Promise.resolve(provisional);
	}

	/**
	 * What an edit reports before the server answers. The overlay already shows
	 * its effect, so this only says what the answer would most likely be.
	 */
	#provisional<R>(op: Op): ActionResult<R> {
		if (op.type === 'item.add') {
			const name = itemName(op.name);
			const same = this.store.itemsOf(op.list_uid).filter((item) => item.name === name);
			if (same.some((item) => !item.done)) {
				return {
					ok: false,
					code: 'duplicate_active',
					message: `'${name}' is already on the list`
				};
			}
			const existing = same[0];
			return {
				ok: true,
				result: { item_uid: existing?.uid ?? op.uid, outcome: existing ? 'restored' : 'added' } as R
			};
		}
		if (op.type === 'item.restore') return { ok: true, result: { item_uid: op.uid } as R };
		return { ok: true, result: {} as R };
	}

	/** An edit that waits for the server's answer (see `#run`). */
	async #runOnline<R = Record<string, never>>(
		op: Op,
		onQueued?: (sent: SentOp) => void
	): Promise<ActionResult<R>> {
		const blocked = this.#guardWrite();
		if (blocked) return blocked;
		const epoch = this.#identityEpoch;
		try {
			const response = await this.#queue.send(op, false, onQueued);
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
	return standaloneLogout(slug, client);
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

/** The server's last-room hint is routing only; it never authorizes access. */
export async function lastRoom(
	client: Pick<Api, 'lastRoom'> = defaultApi,
	snapshots: Pick<SnapshotStore, 'lastRoom'> = browserSnapshots()
): Promise<string | null> {
	try {
		return await client.lastRoom();
	} catch (error) {
		const temporary =
			error instanceof NetworkError ||
			(error instanceof ApiError &&
				([502, 503, 504].includes(error.status) || error.code === 'unavailable'));
		if (!temporary) throw error;
		const saved = await snapshots.lastRoom();
		if (!saved.ok) throw error;
		return saved.value;
	}
}
