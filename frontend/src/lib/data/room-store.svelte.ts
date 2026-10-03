// The reactive data of one room: server state from the changes feed, with
// pending local ops projected on top (see overlay.ts).

import { ApiError } from './types';
import type { Feed, Item, List, OpResponse, Room, SentOp } from './types';
import { isProjected, nowIso, project, type PendingOp, type RoomData } from './overlay';
import { groupItemsByList, sortLists } from './order';
import { mergeFeed } from './feed';
import { filterVisibleItems } from './visibility';
import type { QueueHost } from './write-queue';

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
export function createRoomStore(slug: string, source: FeedSource): RoomStore {
	let store: RoomStore | undefined;
	$effect.root(() => {
		store = new RoomStore(slug, source);
	});
	// Code compiled for the server (also unit tests in Node) has no effects,
	// so `$effect.root` does not call us there: create the store directly.
	return store ?? new RoomStore(slug, source);
}

export class RoomStore implements QueueHost {
	readonly slug: string;
	readonly #source: FeedSource;

	room = $state.raw<Room | null>(null);
	/** The room `seq` of the last applied feed; sent as `since` next time. */
	seq = $state(0);
	status = $state<RoomStatus>('loading');
	/** The last refresh error, if the data may be out of date. */
	error = $state<string | null>(null);
	notice = $state.raw<Notice | null>(null);

	#server = $state.raw<RoomData>(EMPTY);
	#pending = $state.raw<readonly PendingOp[]>([]);
	#view = $derived(project(this.#server, this.#pending));

	/** All lists, sorted by name ignoring case (pending ops included). */
	lists = $derived(sortLists(this.#view.lists.values()));
	#itemsByList = $derived(groupItemsByList(this.#view.items));

	#noticeId = 0;
	#inflight: Promise<void> | null = null;
	#queued: Promise<void> | null = null;
	/** The op whose answer is open. While set, no feed is applied. */
	#sending: string | null = null;
	/** A refresh that waits for that answer. */
	#held: { promise: Promise<void>; resolve: () => void } | null = null;

	constructor(slug: string, source: FeedSource) {
		this.slug = slug;
		this.#source = source;
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
	refresh(): Promise<void> {
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

	async #load(): Promise<void> {
		try {
			const feed = await this.#source.changes(this.slug, this.seq);
			if (this.#sending !== null) {
				// A write went out meanwhile: read again after its answer.
				void this.#hold();
				return;
			}
			this.applyFeed(feed);
			this.error = null;
			this.status = 'ready';
		} catch (error) {
			if (error instanceof ApiError && error.status === 401) {
				this.authRequired();
				return;
			}
			this.error = error instanceof Error ? error.message : String(error);
			if (this.status === 'loading') this.status = 'error';
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
		this.#server = EMPTY;
		this.#pending = [];
		this.room = null;
		this.seq = 0;
		this.error = null;
		this.status = status;
		this.#sending = null;
		this.#held?.resolve();
		this.#held = null;
	}

	#hold(): Promise<void> {
		if (!this.#held) {
			let resolve!: () => void;
			const promise = new Promise<void>((done) => {
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
		if (!held && !refresh) return;
		const done = this.refresh();
		if (held) void done.then(held.resolve);
	}

	// QueueHost: the write queue reports what happens to each op.

	opQueued(op: SentOp): void {
		if (!isProjected(op)) return;
		this.#pending = [...this.#pending, { op, at: nowIso(), appliedSeq: null }];
	}

	opSending(op: SentOp): void {
		this.#sending = op.op_id;
	}

	opSettled(op: SentOp, response: OpResponse): void {
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
		this.#drop(op.op_id);
		if (error instanceof ApiError) this.notify(error.code, error.message);
		else this.notify('unknown', 'The change could not be saved.');
		this.#answered(false);
	}

	opUnanswered(op: SentOp, maybeApplied: boolean): void {
		// Live updates go on while the op is retried; a feed may then contain it.
		if (maybeApplied) this.#update(op.op_id, { uncertain: true });
		this.#answered(false);
	}

	authRequired(): void {
		this.status = 'auth_required';
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
