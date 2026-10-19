// The reactive data of one room: server state from the changes feed, with
// pending local ops projected on top (see overlay.ts).

import { SvelteMap, SvelteSet } from 'svelte/reactivity';
import { compat } from './compat.svelte';
import { ApiError, NetworkError } from './types';
import { failed, isActionCode, type ActionCode } from './result';
import type { Feed, Item, List, OpResponse, Room, SentOp } from './types';
import {
	isProjected,
	nowIso,
	project,
	projectRoom,
	type AnsweredSeq,
	type PendingOp,
	type RoomData
} from './overlay';
import { changedRow, type Rewrite } from './rebase';
import { countsAsWaited, notSavedMessage, unsentRows } from './not-saved';
import { isSentOp } from './queue-entries';
import { isRecord } from './snapshot-validate';
import { groupItemsByList, sortLists } from './order';
import { mergeFeed } from './feed';
import { filterVisibleItems } from './visibility';
import type { QueueHost } from './write-queue';
import type { LiveHost, LiveState } from './events';
import type { SavedSnapshot, SnapshotData } from './snapshot-store';

export type RoomStatus = 'loading' | 'ready' | 'auth_required' | 'error';

/** A message for the user, such as a rejected change. A new `id` means a new message. */
export interface Notice {
	id: number;
	code: ActionCode;
	message: string;
}

/**
 * A change the server refused, or failed, after it waited (see `countsAsWaited`).
 * Stored with this room's device-local queue until dismissal or a successful retry.
 */
export interface NotSavedChange {
	id: number;
	/** Stable across tabs and retries: the original rejected op id. */
	key: string;
	/** The op as it was sent; "Save mine anyway" sends its body again. */
	op: SentOp;
	code: ActionCode;
	message: string;
	name: string | null;
	/** The active explicit retry, if one is waiting for its answer. */
	retryOpId?: string;
	/** What and why, in plain words. */
	text: string;
}

/** How an op this page knows about was made. Dropped when it is answered or discarded. */
interface OpTrack {
	queuedAt: number;
	offline: boolean;
	loaded: boolean;
	/** The name the user saw when acting; the answer may come after it changed. */
	name: string | null;
}

export interface FeedSource {
	changes(slug: string, since: number): Promise<Feed>;
}

export interface RoomStoreLifecycle {
	beforeApply?: () => Promise<boolean>;
	/** True while the owner is about to clear the view itself (logout storing its marker). */
	deferClear?: () => boolean;
	feedApplied?: (data: SnapshotData) => Promise<void>;
	unauthorized?: () => void;
	feedFailed?: () => void;
	connectionLost?: () => void;
	persistNotSaved?: (
		change: NotSavedChange | null,
		removedKeys: readonly string[],
		add: boolean
	) => void;
}

const EMPTY: RoomData = { lists: new Map(), items: new Map() };
const NO_ITEMS: readonly Item[] = Object.freeze([]);

/**
 * Creates a room store that lives as long as the browser page, not as long as
 * the component that opened it.
 *
 * Svelte ties each `$derived` to the effect that runs while it is created, and
 * freezes it when that effect ends (the `derived_inert` warning). Rooms are
 * opened inside a page's effect but outlive the page (see `openRoom`), so the
 * store is created in its own effect root, which never ends.
 */
export function createRoomStore(
	slug: string,
	source: FeedSource,
	lifecycle?: RoomStoreLifecycle
): RoomStore {
	let store: RoomStore | undefined;
	$effect.root(() => {
		store = new RoomStore(slug, source, lifecycle);
	});
	// Code compiled for the server (also unit tests in Node) has no effects,
	// so `$effect.root` does not call us there: create the store directly.
	return store ?? new RoomStore(slug, source, lifecycle);
}

export class RoomStore implements QueueHost, LiveHost {
	readonly slug: string;
	readonly #source: FeedSource;
	readonly #lifecycle: RoomStoreLifecycle;

	/** The room as the server sent it (see `room` for the projected name). */
	#serverRoom = $state.raw<Room | null>(null);
	/** The room `seq` of the last applied feed; sent as `since` next time. */
	seq = $state(0);
	status = $state<RoomStatus>('loading');
	/** The last refresh error, if the data may be out of date. */
	error = $state<string | null>(null);
	/** True when the last error was "no connection" (not a server error answer). */
	unreachable = $state(false);
	notice = $state.raw<Notice | null>(null);
	/** The live-updates stream (see `LiveState`). */
	live = $state<LiveState>('stopped');
	/** Writes not answered by the server yet. */
	queued = $state(0);
	/** Refused or failed changes that waited, for the user to look at (6.3). */
	notSaved = $state.raw<readonly NotSavedChange[]>([]);
	/** True while a write got no answer and is being tried again. */
	retrying = $state(false);
	/** When available, the refresh time of the saved view. */
	savedAt = $state<string | null>(null);
	/** Storage failures are informational; online data use continues. */
	snapshotWarning = $state<string | null>(null);

	#server = $state.raw<RoomData>(EMPTY);
	#pending = $state.raw<readonly PendingOp[]>([]);
	/** Rows (`item:<uid>`, `list:<uid>`) with a change not answered yet. */
	#unsent = $derived(unsentRows(this.#pending));
	#tracks = new SvelteMap<string, OpTrack>();
	/** Rows that answered ops changed, until the feed has them (see AnsweredSeq). */
	#answeredRows = $state.raw<readonly AnsweredSeq[]>([]);
	#view = $derived(project(this.#server, this.#pending, this.#answeredRows));
	#projectedRoom = $derived(projectRoom(this.#serverRoom, this.#pending));

	/** All lists, sorted by name ignoring case (pending ops included). */
	lists = $derived(sortLists(this.#view.lists.values()));
	#itemsByList = $derived(groupItemsByList(this.#view.items));

	#noticeId = 0;
	#notSavedId = 0;
	#signoutHeld = new SvelteMap<string, string | null>();
	#inflight: Promise<boolean> | null = null;
	#queued: Promise<boolean> | null = null;
	#clearVersion = 0;
	#feedVersion = 0;
	#cleared = false;
	#writeAuthorized = $state(false);
	/** Set once data is confirmed or saved for this room; cleared when it goes. */
	#editable = $state(false);
	#savedView = $state(false);
	#authorizationVersion = 0;
	#sentAuthorization = new SvelteMap<string, number>();
	#sentClearVersion = new SvelteMap<string, number>();
	/** The op whose answer is open. While set, no feed is applied. */
	#sending: string | null = null;
	/** A refresh that waits for that answer. */
	#held: { promise: Promise<boolean>; resolve: (refreshed: boolean) => void } | null = null;

	constructor(slug: string, source: FeedSource, lifecycle: RoomStoreLifecycle = {}) {
		this.slug = slug;
		this.#source = source;
		this.#lifecycle = lifecycle;
	}

	/** The room's name, with a pending rename shown at once. */
	get room(): Room | null {
		return this.#projectedRoom;
	}

	/**
	 * Edits may start: the data is this room's (confirmed or saved) and no new
	 * server version was seen. Offline, an edit is queued and sent later (R9
	 * decides what happens if access is gone then).
	 */
	get canEdit(): boolean {
		return this.#editable && this.status === 'ready' && !compat.incompatible;
	}

	/** Lets `canEdit` go false at once, for example when a sign-out starts. */
	setEditable(editable: boolean): void {
		this.#editable = editable;
	}

	/** Cached identity and data never authorize writes. */
	get canWrite(): boolean {
		return (
			this.#writeAuthorized &&
			this.status === 'ready' &&
			this.error === null &&
			!compat.incompatible
		);
	}

	get readOnly(): boolean {
		return !this.canWrite;
	}

	/**
	 * Showing data that this page has not confirmed with the server: a saved
	 * view not yet refreshed, the last data after a failed load, or a lost
	 * live connection. Unlike
	 * `readOnly`, it is not true during an ordinary online revalidation.
	 */
	get unconfirmedView(): boolean {
		return this.#savedView || this.error !== null || this.live === 'reconnecting';
	}

	/**
	 * True while the page shows the offline notice. Then the notice is the only
	 * connection message: the pill and the network "latest changes" error hide.
	 */
	get showsOfflineNotice(): boolean {
		return this.readOnly && this.unconfirmedView && Boolean(this.savedAt);
	}

	/** Shows server data from this session's last good read (not a saved view). */
	get confirmed(): boolean {
		return this.status === 'ready' && !this.#savedView && this.error === null;
	}

	setWriteAuthorized(authorized: boolean): void {
		if (this.#writeAuthorized !== authorized) this.#authorizationVersion += 1;
		this.#writeAuthorized = authorized;
	}

	/** Applies a validated saved view for display only; it never restores access. */
	hydrate(snapshot: SavedSnapshot): void {
		this.#clearVersion += 1;
		this.#cleared = false;
		this.#server = {
			lists: new SvelteMap(snapshot.lists.map((list) => [list.uid, list])),
			items: new SvelteMap(snapshot.items.map((item) => [item.uid, item]))
		};
		this.#serverRoom = snapshot.room;
		this.#answeredRows = [];
		this.seq = snapshot.seq;
		this.savedAt = snapshot.savedAt;
		this.error = null;
		this.status = 'ready';
		this.#editable = true;
		this.#savedView = true;
		this.setWriteAuthorized(false);
	}

	/** A room-only endpoint lost membership; the independently valid share view stays. */
	dropMemberRoom(): void {
		this.#feedVersion += 1;
		this.#serverRoom = null;
		this.setWriteAuthorized(false);
	}

	setSnapshotWarning(message: string | null): void {
		this.snapshotWarning = message;
	}

	reportLoadFailure(error: unknown): void {
		this.setWriteAuthorized(false);
		this.error = error instanceof Error ? error.message : String(error);
		this.unreachable = error instanceof NetworkError;
		if (this.status === 'loading') this.status = 'error';
	}

	/** True while the last read failed, so the data may be out of date. */
	get stale(): boolean {
		return this.error !== null || this.status === 'error';
	}

	/** Server state only, without pending ops. */
	get server(): RoomData {
		return this.#server;
	}

	get pendingOps(): readonly PendingOp[] {
		return this.#pending;
	}

	list(uid: string): List | undefined {
		return this.#view.lists.get(uid);
	}

	listBySlug(slug: string): List | undefined {
		return this.lists.find((list) => list.slug === slug);
	}

	item(uid: string): Item | undefined {
		return this.#view.items.get(uid);
	}

	/** The items of a list: open first, then by name. */
	itemsOf(listUid: string): readonly Item[] {
		return this.#itemsByList.get(listUid) ?? NO_ITEMS;
	}

	/** The items of a list that the hide-done setting shows. */
	visibleItemsOf(listUid: string, now?: Date): Item[] {
		const list = this.list(listUid);
		const items = this.itemsOf(listUid);
		return list ? filterVisibleItems(items, list.hide_done, now) : [...items];
	}

	/**
	 * Applies one changes feed. A full feed replaces everything; a delta upserts
	 * by `uid` and removes deletions. Returns false for a delta older than ours.
	 */
	applyFeed(feed: Feed): boolean {
		if (!feed.full && feed.seq < this.seq) return false;
		const restored = feed.full && feed.seq < this.seq;

		this.#server = mergeFeed(this.#server, feed);
		this.#cleared = false;
		this.#serverRoom = feed.room;
		this.seq = feed.seq;
		// An applied op is in the data once we reached its seq. After a database
		// restore (full feed with a lower seq) the old seqs mean nothing.
		this.#pending = this.#pending.filter(
			(pending) => pending.appliedSeq === null || (!restored && pending.appliedSeq > this.seq)
		);
		// The feed has the rows up to its seq; answers it does not reach are kept.
		this.#answeredRows = restored
			? []
			: this.#answeredRows.filter((row) => row.appliedSeq > this.seq);
		return true;
	}

	/**
	 * Reads the changes since our `seq`. At most one request runs, and at most
	 * one more is queued; later calls share the queued one.
	 *
	 * While a write's answer is open, the refresh waits for it: a feed may
	 * already contain that write while its projection is still shown, which
	 * would count it twice (or make a toggled tag flicker).
	 */
	refresh(): Promise<boolean> {
		if (this.#sending !== null) return this.#hold();
		if (!this.#inflight) {
			this.#inflight = this.#load().finally(() => {
				this.#inflight = null;
			});
			return this.#inflight;
		}
		this.#queued ??= this.#inflight.then(() => {
			this.#queued = null;
			return this.refresh();
		});
		return this.#queued;
	}

	/**
	 * Resolves once our data has reached `seq`, or after one more refresh
	 * (it may fail). Joins a running refresh instead of starting an extra one.
	 */
	async catchUp(seq: number): Promise<void> {
		if (this.seq >= seq) return;
		if (this.#inflight) {
			await this.#inflight;
			if (this.seq >= seq) return;
		}
		await this.refresh();
	}

	async #load(): Promise<boolean> {
		const clearVersion = this.#clearVersion;
		const feedVersion = this.#feedVersion;
		try {
			const feed = await this.#source.changes(this.slug, this.seq);
			if (clearVersion !== this.#clearVersion || feedVersion !== this.#feedVersion) return false;
			if (this.#sending !== null) {
				// A write went out meanwhile: read again after its answer.
				void this.#hold();
				return false;
			}
			if (this.#lifecycle.beforeApply && !(await this.#lifecycle.beforeApply())) {
				if (clearVersion === this.#clearVersion && !this.#lifecycle.deferClear?.()) {
					this.clear('auth_required');
				}
				return false;
			}
			if (clearVersion !== this.#clearVersion || feedVersion !== this.#feedVersion) return false;
			if (!this.applyFeed(feed)) return false;
			this.error = null;
			this.status = 'ready';
			this.#editable = true;
			this.#savedView = false;
			if (this.#lifecycle.feedApplied) {
				await this.#lifecycle.feedApplied({
					seq: this.seq,
					room: this.#serverRoom,
					lists: [...this.#server.lists.values()],
					items: [...this.#server.items.values()]
				});
			}
			return clearVersion === this.#clearVersion && feedVersion === this.#feedVersion;
		} catch (error) {
			if (clearVersion !== this.#clearVersion || feedVersion !== this.#feedVersion) return false;
			if (error instanceof ApiError && error.status === 401) {
				this.authRequired();
				return false;
			}
			this.error = error instanceof Error ? error.message : String(error);
			this.unreachable = error instanceof NetworkError;
			this.setWriteAuthorized(false);
			this.#lifecycle.feedFailed?.();
			if (this.status === 'loading') this.status = 'error';
			return false;
		}
	}

	/** Shows a message to the user (see `notice`). */
	notify(code: ActionCode, message: string): void {
		this.#noticeId += 1;
		this.notice = { id: this.#noticeId, code, message };
	}

	dismissNotice(): void {
		this.notice = null;
	}

	/** Forgets all room data, for example after signing out. */
	clear(status: RoomStatus = 'auth_required'): void {
		this.#clearVersion += 1;
		this.#cleared = true;
		this.setWriteAuthorized(false);
		this.#server = EMPTY;
		this.#pending = [];
		this.#answeredRows = [];
		this.#serverRoom = null;
		this.#editable = false;
		this.seq = 0;
		this.savedAt = null;
		this.#savedView = false;
		this.error = null;
		this.notice = null;
		this.status = status;
		this.queued = 0;
		this.retrying = false;
		this.#sending = null;
		this.#sentClearVersion.clear();
		this.#sentAuthorization.clear();
		this.#held?.resolve(false);
		this.#held = null;
		this.#tracks.clear();
	}

	#hold(): Promise<boolean> {
		if (!this.#held) {
			let resolve!: (refreshed: boolean) => void;
			const promise = new Promise<boolean>((done) => {
				resolve = done;
			});
			this.#held = { promise, resolve };
		}
		return this.#held.promise;
	}

	/** The open answer came (or will not come for now): run the held refresh. */
	#answered(refresh: boolean): void {
		this.#sending = null;
		const held = this.#held;
		this.#held = null;
		if ((!held && !refresh) || this.#cleared) {
			held?.resolve(false);
			return;
		}
		const done = this.refresh();
		if (held) void done.then((refreshed) => held.resolve(refreshed));
	}

	// QueueHost: the write queue reports what happens to each op.

	/** Recount retained queue entries after a clear, without projecting them again. */
	syncQueued(count: number): void {
		this.queued = count;
		this.retrying = false;
	}

	opQueued(op: SentOp, offline = false): void {
		this.#sentClearVersion.set(op.op_id, this.#clearVersion);
		this.#waiting(op, nowIso(), { offline, loaded: false });
	}

	/**
	 * A stored op read again (see WriteQueue.load). It keeps the send generation
	 * it had, so an op that is still in flight is not taken for a new one.
	 * `sent`: its request may have gone out before the reload, so the server may
	 * already have it. Its projection is then uncertain (see `project`).
	 */
	opLoaded(op: SentOp, at: string, sent: boolean): void {
		this.#waiting(op, at, { offline: false, loaded: true }, sent);
	}

	#waiting(op: SentOp, at: string, how: Pick<OpTrack, 'offline' | 'loaded'>, sent = false): void {
		if (!this.#tracks.has(op.op_id)) {
			const parsed = Date.parse(at);
			this.#tracks.set(op.op_id, {
				queuedAt: Number.isNaN(parsed) ? Date.now() : parsed,
				...how,
				name: this.#nameOf(op)
			});
		}
		// Already shown (the queue was read again): nothing to add.
		if (this.#pending.some((pending) => pending.op.op_id === op.op_id)) return;
		this.queued += 1;
		if (!isProjected(op)) return;
		this.#pending = [
			...this.#pending,
			{ op, at, appliedSeq: null, ...(sent ? { uncertain: true } : {}) }
		];
	}

	/** A waiting op was dropped by the user: its change is no longer shown. */
	opDiscarded(op: SentOp): void {
		this.#tracks.delete(op.op_id);
		this.#drop(op.op_id);
		this.queued = Math.max(0, this.queued - 1);
		this.#signoutHeld.delete(op.op_id);
		const retry = this.#retryChange(op);
		if (retry) this.#retryStopped(retry);
	}

	/** The item or list name the user sees for this op's row, or null. */
	#nameOf(op: SentOp): string | null {
		if ('item_uid' in op) return this.#view.items.get(op.item_uid)?.name ?? null;
		if (op.type.startsWith('list.') && 'list_uid' in op) {
			return this.#view.lists.get(op.list_uid)?.name ?? null;
		}
		return null;
	}

	/**
	 * Whether a settled op counts as waited (see `countsAsWaited`), with the
	 * name to show. Forgets the op's track.
	 */
	#settleTrack(op: SentOp): { waited: boolean; name: string | null } {
		const track = this.#tracks.get(op.op_id);
		this.#tracks.delete(op.op_id);
		const waited = track
			? countsAsWaited({
					offline: track.offline,
					loaded: track.loaded,
					queuedAt: track.queuedAt,
					answeredAt: Date.now()
				})
			: false;
		return { waited, name: track?.name ?? this.#nameOf(op) };
	}

	/** Restores validated rejections from this room's device-local queue record. */
	loadNotSaved(values: readonly unknown[]): void {
		const seen = new SvelteSet<string>();
		const restored: NotSavedChange[] = [];
		for (const value of values) {
			if (!isRecord(value)) continue;
			const { id, op, code, message, name, retryOpId } = value;
			if (
				!Number.isSafeInteger(id) ||
				(id as number) < 1 ||
				!isSentOp(op) ||
				typeof code !== 'string' ||
				typeof message !== 'string' ||
				!(name === null || typeof name === 'string') ||
				!(retryOpId === undefined || typeof retryOpId === 'string')
			)
				continue;
			const key = typeof value.key === 'string' ? value.key : op.op_id;
			if (seen.has(key)) continue;
			seen.add(key);
			// A code this build does not know reads as unknown; its message still shows.
			const known = isActionCode(code) ? code : 'unknown';
			const parsed: NotSavedChange = {
				id: ++this.#notSavedId,
				key,
				op,
				code: known,
				message,
				name,
				...(typeof retryOpId === 'string' ? { retryOpId } : {}),
				text: notSavedMessage({ op, code: known, message, name })
			};
			restored.push(parsed);
		}
		this.notSaved = restored;
	}

	/** Associates a deliberate retry with its rejection until the answer arrives. */
	markNotSavedRetry(id: number, retryOpId: string): boolean {
		const change = this.notSaved.find((item) => item.id === id);
		if (!change || change.retryOpId) return false;
		this.notSaved = this.notSaved.map((item) => (item.id === id ? { ...item, retryOpId } : item));
		this.#persistNotSaved(this.notSaved.find((item) => item.id === id)!);
		return true;
	}

	/** Puts a refused or failed change on the Not saved list. */
	#collect(op: SentOp, code: ActionCode, message: string, name: string | null): void {
		this.#notSavedId += 1;
		const text = notSavedMessage({ op, code, message, name });
		const change = { id: this.#notSavedId, key: op.op_id, op, code, message, name, text };
		this.notSaved = [...this.notSaved, change];
		this.#persistNotSaved(change, [], true);
	}

	#persistNotSaved(
		change: NotSavedChange | null,
		removedKeys: readonly string[] = [],
		add = false
	): void {
		this.#lifecycle.persistNotSaved?.(change, removedKeys, add);
	}

	#retryChange(op: SentOp): NotSavedChange | undefined {
		return this.notSaved.find((change) => change.retryOpId === op.op_id);
	}

	#retryFailed(change: NotSavedChange, op: SentOp, code: ActionCode, message: string): void {
		const text = notSavedMessage({ op, code, message, name: change.name });
		this.notSaved = this.notSaved.map((item) =>
			item.id === change.id ? { ...item, op, code, message, text, retryOpId: undefined } : item
		);
		this.#persistNotSaved(this.notSaved.find((item) => item.key === change.key)!);
	}

	#retryFinished(change: NotSavedChange): void {
		this.notSaved = this.notSaved.filter((item) => item.id !== change.id);
		this.#persistNotSaved(null, [change.key]);
	}

	#retryStopped(change: NotSavedChange): void {
		this.notSaved = this.notSaved.map((item) =>
			item.id === change.id ? { ...item, retryOpId: undefined } : item
		);
		this.#persistNotSaved(this.notSaved.find((item) => item.key === change.key)!);
	}

	/** Removes an entry from the Not saved list (the user dismissed it). */
	dismissNotSaved(id: number): void {
		const change = this.notSaved.find((item) => item.id === id);
		if (!change) return;
		this.notSaved = this.notSaved.filter((item) => item.id !== id);
		this.#persistNotSaved(null, [change.key]);
	}

	dismissAllNotSaved(): void {
		const keys = this.notSaved.map((change) => change.key);
		this.notSaved = [];
		this.#persistNotSaved(null, keys);
	}

	/** Takes an entry off the Not saved list, to send it again. */
	takeNotSaved(id: number): NotSavedChange | undefined {
		const change = this.notSaved.find((item) => item.id === id);
		if (change) this.dismissNotSaved(id);
		return change;
	}

	/** True when a change on this row (`item:<uid>` or `list:<uid>`) is not sent yet. */
	isUnsent(row: string): boolean {
		return this.#unsent.has(row);
	}

	/** Later ops were rewritten (base_seq or uid): keep the projection in step. */
	opsRewritten(rewrites: readonly Rewrite[]): void {
		this.#pending = this.#pending.map((pending) => {
			const rewrite = rewrites.find((item) => item.opId === pending.op.op_id);
			return rewrite ? { ...pending, op: rewrite.op } : pending;
		});
	}

	/**
	 * The `changed_seq` of a row as this device shows it, for rebasing (rebase.ts).
	 * Read before the answer is recorded (the queue plans first).
	 */
	knownSeq(row: string): number | undefined {
		const uid = row.slice(row.indexOf(':') + 1);
		if (row.startsWith('list:')) return this.#view.lists.get(uid)?.changed_seq;
		return this.#view.items.get(uid)?.changed_seq;
	}

	/** An applied change shows its row's new `changed_seq` at once (see AnsweredSeq). */
	#recordAnswer(op: SentOp, response: OpResponse): void {
		if (response.status !== 'applied' || typeof response.result.changed_seq !== 'number') return;
		const row = changedRow(op, response);
		if (row === null) return;
		this.#answeredRows = [
			...this.#answeredRows.filter((answered) => answered.row !== row),
			{ row, changed_seq: response.result.changed_seq, appliedSeq: response.seq }
		];
	}

	opsHeldForSignOut(ops: readonly SentOp[]): void {
		for (const op of ops) this.#signoutHeld.set(op.op_id, this.#nameOf(op));
	}

	opSending(op: SentOp): void {
		this.#sending = op.op_id;
		this.#sentAuthorization.set(op.op_id, this.#authorizationVersion);
		this.#sentClearVersion.set(op.op_id, this.#clearVersion);
	}

	opSettled(op: SentOp, response: OpResponse): void {
		if (!this.#currentOp(op)) {
			if (!this.#signoutHeld.has(op.op_id)) return;
			const retry = this.#retryChange(op);
			const name = this.#signoutHeld.get(op.op_id) ?? null;
			this.#signoutHeld.delete(op.op_id);
			if (response.status === 'rejected') {
				if (retry) this.#retryFailed(retry, op, response.code, response.message);
				else if (!(op.type === 'item.add' && response.code === 'duplicate_active'))
					this.#collect(op, response.code, response.message, name);
			} else if (retry) this.#retryFinished(retry);
			return;
		}
		this.#signoutHeld.delete(op.op_id);
		const { waited, name } = this.#settleTrack(op);
		this.#sentClearVersion.delete(op.op_id);
		this.#done();
		this.#sentAuthorization.delete(op.op_id);
		this.#recordAnswer(op, response);
		const retry = this.#retryChange(op);
		if (response.status === 'rejected') {
			this.#drop(op.op_id);
			if (retry) {
				if (waited) this.#retryFailed(retry, op, response.code, response.message);
				else this.#retryStopped(retry);
			} else if (op.type === 'item.add' && response.code === 'duplicate_active' && waited) {
				// R6: the item is on the list already, which is what the add wanted.
				// Nothing to tell the user; the later changes went to that item.
			} else if (waited) this.#collect(op, response.code, response.message, name);
			else this.notify(response.code, response.message);
		} else {
			if (retry) this.#retryFinished(retry);
			if (response.seq <= this.seq) {
				this.#drop(op.op_id);
			} else {
				// Our data is older than the op (a replay answers with the op's own
				// seq), so it does not contain it: project it until the feed has it.
				this.#update(op.op_id, { appliedSeq: response.seq, uncertain: false });
			}
		}
		// Someone (maybe this op) changed the room: read the changes.
		this.#answered(response.seq > this.seq);
	}

	opFailed(op: SentOp, error: unknown): void {
		const { code, message } = failed(error);
		if (!this.#currentOp(op)) {
			if (!this.#signoutHeld.has(op.op_id)) return;
			const retry = this.#retryChange(op);
			const name = this.#signoutHeld.get(op.op_id) ?? null;
			this.#signoutHeld.delete(op.op_id);
			if (retry) this.#retryFailed(retry, op, code, message);
			else this.#collect(op, code, message, name);
			return;
		}
		this.#signoutHeld.delete(op.op_id);
		const { waited, name } = this.#settleTrack(op);
		this.#sentClearVersion.delete(op.op_id);
		this.#done();
		this.#sentAuthorization.delete(op.op_id);
		this.#drop(op.op_id);
		const retry = this.#retryChange(op);
		if (retry) {
			if (waited) this.#retryFailed(retry, op, code, message);
			else this.#retryStopped(retry);
		} else if (waited) this.#collect(op, code, message, name);
		else this.notify(code, message);
		this.#answered(false);
	}

	opUnanswered(op: SentOp, maybeApplied: boolean): void {
		if (!this.#currentOp(op)) return;
		// 401 (`maybeApplied` false): it waits for sign-in, not for the server.
		this.retrying = maybeApplied;
		// Live updates go on while the op is retried; a feed may then contain it.
		if (maybeApplied) this.#update(op.op_id, { uncertain: true });
		this.#answered(false);
	}

	authRequired(op?: SentOp): 'current' | 'stale' | 'blocked' | void {
		if (op && !this.#currentOp(op)) return this.canWrite ? 'stale' : 'blocked';
		const sentGeneration = op ? this.#sentAuthorization.get(op.op_id) : undefined;
		if (op) this.#sentAuthorization.delete(op.op_id);
		if (sentGeneration !== undefined && sentGeneration !== this.#authorizationVersion) {
			return this.canWrite ? 'stale' : 'blocked';
		}
		this.setWriteAuthorized(false);
		this.status = 'auth_required';
		this.#lifecycle.unauthorized?.();
		return 'current';
	}

	liveChanged(state: LiveState): void {
		this.live = state;
		if (state === 'reconnecting') {
			this.setWriteAuthorized(false);
			this.#lifecycle.connectionLost?.();
		}
	}

	#currentOp(op: SentOp): boolean {
		return this.#sentClearVersion.get(op.op_id) === this.#clearVersion;
	}

	#done(): void {
		this.queued = Math.max(0, this.queued - 1);
		this.retrying = false;
	}

	#update(opId: string, changes: Partial<PendingOp>): void {
		this.#pending = this.#pending.map((pending) =>
			pending.op.op_id === opId ? { ...pending, ...changes } : pending
		);
	}

	#drop(opId: string): void {
		this.#pending = this.#pending.filter((pending) => pending.op.op_id !== opId);
	}
}
