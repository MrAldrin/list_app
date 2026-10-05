// The client data layer: the one entry point for pages and components.
//
//   const room = openRoom(slug);       // start: load data, live updates
//   room.store.lists                   // reactive data (see RoomStore)
//   await room.addItem(list, 'milk');  // writes: { ok, result } or { ok: false, message }
//   closeRoom(room);                   // stop live updates
//
// Components never call `fetch` themselves.

import { Api, api as defaultApi } from './api';
import { LiveUpdates, type EventSourceFactory, type SessionState } from './events';
import { newId } from './ids';
import { createRoomStore, RoomStore, type RoomStatus } from './room-store.svelte';
import { ApiError } from './types';
import type {
	HideDone,
	Item,
	ItemAddResult,
	ItemRestoreResult,
	List,
	ListCreateResult,
	Op,
	Room
} from './types';
import { WriteQueue } from './write-queue';

export * from './types';
export type { RoomStatus, Notice } from './room-store.svelte';
export type { LiveState } from './events';
export { connectionStatus, CONNECTION_STATUS_DELAY, type ConnectionStatus } from './status';
export { RoomStore } from './room-store.svelte';
export { filterVisibleItems, DEFAULT_HIDE_DONE, MAX_HIDE_DONE_COUNT } from './visibility';
export { sortItems, sortLists, sortTags } from './order';
export { newId } from './ids';

export type ActionResult<R = Record<string, never>> =
	{ ok: true; result: R } | { ok: false; code: string; message: string };

type ListRef = Pick<List, 'uid'>;
type ItemRef = Pick<Item, 'uid' | 'list_uid'>;

/** The API calls a room needs; tests pass a fake. */
export type RoomApi = Pick<
	Api,
	'changes' | 'sendOp' | 'login' | 'whoAmI' | 'eventsUrl' | 'changePassword' | 'deleteRoom'
>;

export interface RoomOptions {
	api?: RoomApi;
	createEventSource?: EventSourceFactory;
	retryDelays?: readonly number[];
	reconnectDelays?: readonly number[];
	visibility?: Pick<
		Document,
		'visibilityState' | 'addEventListener' | 'removeEventListener'
	> | null;
}

/** One room: its data (`store`), its write queue and its live updates. */
export class RoomHandle {
	readonly slug: string;
	readonly store: RoomStore;
	readonly #api: RoomApi;
	readonly #queue: WriteQueue;
	readonly #live: LiveUpdates;
	/** Deleted items, kept so `restoreItem` can bring them back. */
	readonly #deleted = new Map<string, Item>();
	/** An open password change: session checks wait for it (see `changePassword`). */
	#passwordChange: Promise<unknown> | null = null;
	#users = 0;

	constructor(slug: string, options: RoomOptions = {}) {
		this.slug = slug;
		this.#api = options.api ?? defaultApi;
		this.store = createRoomStore(slug, this.#api);
		this.#queue = new WriteQueue(slug, this.#api, this.store, {
			retryDelays: options.retryDelays
		});
		this.#live = new LiveUpdates({
			url: this.#api.eventsUrl(slug),
			host: this.store,
			checkSession: () => this.#checkSession(),
			onReconnect: () => this.#queue.retryNow(),
			createEventSource: options.createEventSource,
			reconnectDelays: options.reconnectDelays,
			visibility: options.visibility
		});
	}

	/** Ops not answered by the server yet. */
	get queuedOps() {
		return this.#queue.pending;
	}

	/** Starts loading and live updates. Pair each call with `release()`. */
	retain(): void {
		this.#users += 1;
		if (this.#users === 1) {
			void this.store.refresh();
			this.#live.start();
		}
	}

	/** Stops live updates when nobody uses the room. Data and queued writes stay. */
	release(): void {
		this.#users = Math.max(0, this.#users - 1);
		if (this.#users === 0) this.#live.stop();
	}

	// Room

	renameRoom(name: string): Promise<ActionResult> {
		return this.#run({ type: 'room.rename', name });
	}

	/**
	 * Changes the room password. Not a queued op: it needs the server now, and
	 * passwords are never stored for retries. The answer brings a new cookie;
	 * all other devices must sign in again.
	 */
	async changePassword(currentPassword: string, newPassword: string): Promise<ActionResult<Room>> {
		const change = this.#api.changePassword(this.slug, currentPassword, newPassword);
		// Our own stream is revoked too. Its "who am I" check must wait for the
		// new cookie, or it would see the old token and sign us out.
		this.#passwordChange = change.catch(() => undefined);
		try {
			return { ok: true, result: await change };
		} catch (error) {
			return failed(error);
		} finally {
			this.#passwordChange = null;
		}
	}

	/** Deletes the room with all its lists and items, then forgets it here. */
	async deleteRoom(password: string): Promise<ActionResult> {
		try {
			await this.#api.deleteRoom(this.slug, password);
		} catch (error) {
			return failed(error);
		}
		// 'loading', not 'auth_required': the page leaves; no password prompt flashes.
		this.#forget('loading');
		if (rooms.get(this.slug) === this) rooms.delete(this.slug);
		return { ok: true, result: {} };
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

	/** Add-or-restore: `outcome` is `added`, or `restored` for a checked item that came back. */
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

	/** Deletes an item and keeps its data, so `restoreItem(item.uid)` can undo it. */
	deleteItem(item: Item): Promise<ActionResult> {
		this.#deleted.set(item.uid, this.store.item(item.uid) ?? item);
		return this.#run({ type: 'item.delete', ...itemKeys(item) });
	}

	/** Undo of `deleteItem`: a new item (new `uid`) with the kept data. */
	async restoreItem(itemUid: string): Promise<ActionResult<ItemRestoreResult>> {
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

	/** Signs in to this room, then reloads and sends the writes that waited. */
	async login(password: string): Promise<ActionResult<Room>> {
		let room: Room;
		try {
			room = await this.#api.login(this.slug, password);
		} catch (error) {
			return failed(error);
		}
		await this.signedIn();
		return { ok: true, result: room };
	}

	/** Call after a successful sign-in to this room. */
	async signedIn(): Promise<void> {
		await this.store.refresh();
		this.#queue.resume();
		if (this.#users > 0) this.#live.start();
	}

	/** Forgets this room's data and queued writes. */
	signedOut(): void {
		this.#forget('auth_required');
	}

	#forget(status: RoomStatus): void {
		this.#live.stop();
		this.#queue.dispose(new ApiError(401, 'not_authenticated', 'Signed out.'));
		this.#deleted.clear();
		this.store.clear(status);
	}

	async #run<R = Record<string, never>>(op: Op): Promise<ActionResult<R>> {
		try {
			const response = await this.#queue.send(op);
			if (response.status === 'rejected') {
				return { ok: false, code: response.code, message: response.message };
			}
			// Resolve once the change is in the store, so the caller can use it.
			await this.store.catchUp(response.seq);
			return { ok: true, result: response.result as R };
		} catch (error) {
			return failed(error);
		}
	}

	async #checkSession(): Promise<SessionState> {
		if (this.#passwordChange) await this.#passwordChange;
		try {
			await this.#api.whoAmI(this.slug);
			return 'signed_in';
		} catch (error) {
			return error instanceof ApiError && error.status === 401 ? 'signed_out' : 'unknown';
		}
	}
}

function itemKeys(item: ItemRef) {
	return { list_uid: item.list_uid, item_uid: item.uid };
}

function failed(error: unknown): { ok: false; code: string; message: string } {
	if (error instanceof ApiError) return { ok: false, code: error.code, message: error.message };
	if (error instanceof Error) return { ok: false, code: 'network', message: error.message };
	return { ok: false, code: 'unknown', message: 'Something went wrong.' };
}

// The open rooms of this page. A room stays here after `closeRoom`, so its
// data shows at once when it opens again and its queued writes keep going.
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

/** Signs in to a room. An open room reloads and sends the writes that waited. */
export async function login(
	slug: string,
	password: string,
	client: Api = defaultApi
): Promise<ActionResult<Room>> {
	const room = rooms.get(slug);
	if (room) return room.login(password);
	try {
		return { ok: true, result: await client.login(slug, password) };
	} catch (error) {
		return failed(error);
	}
}

/** Signs out of a room and forgets its data. */
export async function logout(slug: string, client: Api = defaultApi): Promise<ActionResult> {
	try {
		await client.logout(slug);
	} catch (error) {
		return failed(error);
	}
	rooms.get(slug)?.signedOut();
	rooms.delete(slug);
	return { ok: true, result: {} };
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

/** The slug of the last room this browser signed in to, or null. */
export function lastRoom(client: Api = defaultApi): Promise<string | null> {
	return client.lastRoom();
}
