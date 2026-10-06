// The reactive data of one room: server state from the changes feed, with
// pending local ops projected on top (see overlay.ts).

import { SvelteMap } from 'svelte/reactivity';
import { ApiError } from './types';
import type { Feed, Item, List, OpResponse, Room, SentOp } from './types';
import { isProjected, nowIso, project, type PendingOp, type RoomData } from './overlay';
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
	code: string;
	message: string;
}

export interface FeedSource {
	changes(slug: string, since: number): Promise<Feed>;
}

export interface RoomStoreLifecycle {
	beforeApply?: () => Promise<boolean>;
	feedApplied?: (data: SnapshotData) => Promise<void>;
	unauthorized?: () => void;
	feedFailed?: () => void;
	connectionLost?: () => void;
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

	room = $state.raw<Room | null>(null);
	/** The room `seq` of the last applied feed; sent as `since` next time. */
	seq = $state(0);
	status = $state<RoomStatus>('loading');
	/** The last refresh error, if the data may be out of date. */
	error = $state<string | null>(null);
	notice = $state.raw<Notice | null>(null);
	/** The live-updates stream (see `LiveState`). */
	live = $state<LiveState>('stopped');
	/** Writes not answered by the server yet. */
	queued = $state(0);
	/** True while a write got no answer and is being tried again. */
	retrying = $state(false);
	/** When available, the refresh time of the read-only saved view. */
	savedAt = $state<string | null>(null);
	/** Storage failures are informational; online data use continues. */
	snapshotWarning = $state<string | null>(null);

	#server = $state.raw<RoomData>(EMPTY);
	#pending = $state.raw<readonly PendingOp[]>([]);
	#view = $derived(project(this.#server, this.#pending));

	/** All lists, sorted by name ignoring case (pending ops included). */
	lists = $derived(sortLists(this.#view.lists.values()));
	#itemsByList = $derived(groupItemsByList(this.#view.items));

	#noticeId = 0;
	#inflight: Promise<boolean> | null = null;
	#queued: Promise<boolean> | null = null;
	#clearVersion = 0;
	#feedVersion = 0;
	#cleared = false;
	#writeAuthorized = $state(false);
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

	/** Cached identity and data never authorize writes. */
	get canWrite(): boolean {
		return this.#writeAuthorized && this.status === 'ready' && this.error === null;
	}

	get readOnly(): boolean {
		return !this.canWrite;
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
		this.room = snapshot.room;
		this.seq = snapshot.seq;
		this.savedAt = snapshot.savedAt;
		this.error = null;
		this.status = 'ready';
		this.setWriteAuthorized(false);
	}

	/** A room-only endpoint lost membership; the independently valid share view stays. */
	dropMemberRoom(): void {
		this.#feedVersion += 1;
		this.room = null;
		this.setWriteAuthorized(false);
	}

	setSnapshotWarning(message: string | null): void {
		this.snapshotWarning = message;
	}

	reportLoadFailure(message: string): void {
		this.setWriteAuthorized(false);
		this.error = message;
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
		this.room = feed.room;
		this.seq = feed.seq;
		// An applied op is in the data once we reached its seq. After a database
		// restore (full feed with a lower seq) the old seqs mean nothing.
		this.#pending = this.#pending.filter(
			(pending) => pending.appliedSeq === null || (!restored && pending.appliedSeq > this.seq)
		);
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
				if (clearVersion === this.#clearVersion) this.clear('auth_required');
				return false;
			}
			if (clearVersion !== this.#clearVersion || feedVersion !== this.#feedVersion) return false;
			if (!this.applyFeed(feed)) return false;
			this.error = null;
			this.status = 'ready';
			if (this.#lifecycle.feedApplied) {
				await this.#lifecycle.feedApplied({
					seq: this.seq,
					room: this.room,
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
			this.setWriteAuthorized(false);
			this.#lifecycle.feedFailed?.();
			if (this.status === 'loading') this.status = 'error';
			return false;
		}
	}

	/** Shows a message to the user (see `notice`). */
	notify(code: string, message: string): void {
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
		this.room = null;
		this.seq = 0;
		this.savedAt = null;
		this.error = null;
		this.notice = null;
		this.status = status;
		this.queued = 0;
		this.retrying = false;
		this.#sending = null;
		this.#sentClearVersion.clear();
		this.#held?.resolve(false);
		this.#held = null;
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

	opQueued(op: SentOp): void {
		this.#sentClearVersion.set(op.op_id, this.#clearVersion);
		this.queued += 1;
		if (!isProjected(op)) return;
		this.#pending = [...this.#pending, { op, at: nowIso(), appliedSeq: null }];
	}

	opSending(op: SentOp): void {
		this.#sending = op.op_id;
		this.#sentAuthorization.set(op.op_id, this.#authorizationVersion);
		this.#sentClearVersion.set(op.op_id, this.#clearVersion);
	}

	opSettled(op: SentOp, response: OpResponse): void {
		if (!this.#currentOp(op)) return;
		this.#sentClearVersion.delete(op.op_id);
		this.#done();
		this.#sentAuthorization.delete(op.op_id);
		if (response.status === 'rejected') {
			this.#drop(op.op_id);
			this.notify(response.code, response.message);
		} else if (response.seq <= this.seq) {
			this.#drop(op.op_id);
		} else {
			// Our data is older than the op (a replay answers with the op's own
			// seq), so it does not contain it: project it until the feed has it.
			this.#update(op.op_id, { appliedSeq: response.seq, uncertain: false });
		}
		// Someone (maybe this op) changed the room: read the changes.
		this.#answered(response.seq > this.seq);
	}

	opFailed(op: SentOp, error: unknown): void {
		if (!this.#currentOp(op)) return;
		this.#sentClearVersion.delete(op.op_id);
		this.#done();
		this.#sentAuthorization.delete(op.op_id);
		this.#drop(op.op_id);
		if (error instanceof ApiError) this.notify(error.code, error.message);
		else this.notify('unknown', 'The change could not be saved.');
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
