// The write queue of one room. Ops are sent in order, one at a time, each with
// its own retry-safe `op_id` (docs/api.md, "Writing: operations").
//
// - No answer, 502, 503 or 504: retry the same op with the same `op_id`, after
//   a growing pause. Later ops wait, so the order is kept.
// - 401: pause. The ops stay queued; `resume()` after signing in sends them.
// - A new server version (see compat.svelte.ts): stop sending. The ops stay
//   queued with their op_ids; nothing is retried or dropped.
// - Any other HTTP error (403, 409, 415, 422, …): that op fails; go on.
// - 200 `applied` or `rejected`: done; go on.
// - Stored ops that are held (older than 30 days) or unreadable (see
//   queue-entries.ts) block the queue until the user sends or discards them.
//
// Queued ops live in storage (queue-storage.ts) until the server answers.
// Sending happens under a Web Lock per room, so one tab sends at a time (R12).
// The host hears when an op goes out and when it comes back, so the room can
// hold back changes feeds while an answer is open (see RoomStore).

import { isRetryable } from './api';
import { BACKOFF_DELAYS, backoffDelay } from './backoff';
import { compat, INCOMPATIBLE_CODE } from './compat.svelte';
import {
	classifyEntry,
	newStoredEntry,
	summarizeEntries,
	type QueueSnapshot,
	type StoredEntry
} from './queue-entries';
import { MemoryQueueStorage, type QueueStorage } from './queue-storage';
import { newId } from './ids';
import { planRewrites, type Rewrite } from './rebase';
import type { SessionLockManager } from './session-transition';
import { ApiError } from './types';
import type { Op, OpResponse, SentOp } from './types';

/** What the queue tells its room. `RoomStore` implements it. */
export interface QueueHost {
	/**
	 * A new op waits (see `send`). `offline`: it was made while the page could
	 * not write, so its answer is one the user did not see at once.
	 */
	opQueued(op: SentOp, offline: boolean): void;
	/**
	 * An op read from storage waits: it is shown as the stored `at` says. `sent`:
	 * its request may have gone out before the reload, so the server may have it.
	 */
	opLoaded(op: SentOp, at: string, sent: boolean): void;
	/** A waiting op was dropped by the user (see `discard`). */
	opDiscarded(op: SentOp): void;
	/** Later waiting ops were rewritten: a new `base_seq` or uid (see rebase.ts). */
	opsRewritten(rewrites: readonly Rewrite[]): void;
	/** The `changed_seq` of a row the server has, as this device knows it. */
	knownSeq(row: string): number | undefined;
	/** The op is on its way; its answer is open. */
	opSending(op: SentOp): void;
	/** The answer is applied or rejected; the host reads the changes it needs. */
	opSettled(op: SentOp, response: OpResponse): void;
	/** The op failed for good (HTTP error); it is dropped. */
	opFailed(op: SentOp, error: unknown): void;
	/** Sign-out held these ops; a late refusal must still be preserved. */
	opsHeldForSignOut?(ops: readonly SentOp[]): void;
	/**
	 * No answer; the op stays queued. `maybeApplied` is true when the server may
	 * have applied it (no answer, 5xx), false when it surely did not (401).
	 */
	opUnanswered(op: SentOp, maybeApplied: boolean): void;
	/** `stale` means this 401 belongs to an older authorization session; retry it. */
	authRequired(op: SentOp): 'current' | 'stale' | 'blocked' | void;
}

export interface OpSender {
	sendOp(slug: string, op: SentOp): Promise<OpResponse>;
}

export interface WriteQueueOptions {
	/** Defaults to memory only. */
	storage?: QueueStorage;
	retryDelays?: readonly number[];
	/** Web Locks for "one tab sends". Default: none (the room passes the browser's). */
	locks?: SessionLockManager | null;
	/** Storage and lock key, for example `room:<slug>`. Defaults to the slug. */
	key?: string;
	now?: () => Date;
	/** Told after every change to what waits here. */
	onChange?: (snapshot: QueueSnapshot) => void;
}

/** Runs `operation` while holding this queue's lock. Without Web Locks it just runs. */
export function withQueueLock<T>(
	key: string,
	operation: () => Promise<T>,
	locks: SessionLockManager | null
): Promise<T> {
	if (!locks) return operation();
	return locks.request(`listr:queue:${encodeURIComponent(key)}`, { mode: 'exclusive' }, operation);
}

interface Waiter {
	resolve: (response: OpResponse) => void;
	reject: (error: unknown) => void;
}

const noop = () => undefined;

export class WriteQueue {
	readonly #slug: string;
	readonly #key: string;
	readonly #sender: OpSender;
	readonly #host: QueueHost;
	readonly #storage: QueueStorage;
	readonly #delays: readonly number[];
	readonly #locks: SessionLockManager | null;
	readonly #now: () => Date;
	readonly #onChange: ((snapshot: QueueSnapshot) => void) | undefined;
	readonly #waiters = new Map<string, Waiter>();

	/** Every stored entry, in send order: this tab's copy of the storage. */
	#entries: StoredEntry[] = [];
	/** Ops whose request was started and not yet answered (in flight or retried). */
	#sent = new Set<string>();
	/** Bumped by each local change. A storage read that overlaps a change is repeated. */
	#version = 0;
	/** Storage calls run one after another, in the order they were made. */
	#chain: Promise<unknown> = Promise.resolve();
	#running = false;
	#paused = false;
	#disposed = false;
	#attempt = 0;
	#inFlight: string | null = null;
	#wake: (() => void) | null = null;

	constructor(slug: string, sender: OpSender, host: QueueHost, options: WriteQueueOptions = {}) {
		this.#slug = slug;
		this.#key = options.key ?? slug;
		this.#sender = sender;
		this.#host = host;
		this.#storage = options.storage ?? new MemoryQueueStorage();
		this.#delays = options.retryDelays ?? BACKOFF_DELAYS;
		this.#locks = options.locks ?? null;
		this.#now = options.now ?? (() => new Date());
		this.#onChange = options.onChange;
	}

	/** Ops not answered yet, oldest first. Unreadable entries are left out (see `waiting`). */
	get pending(): readonly SentOp[] {
		const now = this.#nowMs();
		return this.#entries.flatMap((entry) => {
			const verdict = classifyEntry(entry, now);
			return verdict.kind === 'unreadable' ? [] : [verdict.op];
		});
	}

	/** Every stored entry that waits, including held and unreadable ones. */
	get waiting(): number {
		return this.#entries.length;
	}

	/** True after a 401, until `resume()`. */
	get paused(): boolean {
		return this.#paused;
	}

	/**
	 * Reads what is stored for this room, so `pending` and `waiting` are right,
	 * and tells the host about each readable op (it projects them, as `send` does).
	 */
	async load(): Promise<void> {
		await this.#readStored();
		const now = this.#nowMs();
		for (const entry of this.#entries) {
			const verdict = classifyEntry(entry, now);
			if (verdict.kind === 'unreadable') continue;
			const at = typeof entry.at === 'string' ? entry.at : this.#now().toISOString();
			this.#host.opLoaded(verdict.op, at, entry.sent === true);
		}
	}

	/**
	 * Queues one op with a new `op_id`. Resolves with the server's answer
	 * (`applied` or `rejected`); rejects with the `ApiError` if the op failed.
	 * `offline`: the page could not write when the user acted (see `QueueHost`).
	 */
	send(op: Op, offline = false, onQueued?: (sent: SentOp) => void): Promise<OpResponse> {
		if (this.#disposed) return Promise.reject(new Error('This room is closed.'));
		const sent = { ...op, op_id: newId() } as SentOp;
		const promise = new Promise<OpResponse>((resolve, reject) => {
			this.#waiters.set(sent.op_id, { resolve, reject });
		});
		const entry = newStoredEntry(sent, this.#now().toISOString());
		this.#entries = [...this.#entries, entry];
		this.#mutated();
		void this.#enqueue(() => this.#storage.add(entry));
		this.#host.opQueued(sent, offline);
		onQueued?.(sent);
		void this.#pump();
		return promise;
	}

	/** Stops future sends while retaining pending ops and their original op_ids. */
	pause(): void {
		this.#paused = true;
		this.#wake?.();
	}

	/** Holds all readable waiting ops until the user chooses after sign-out. */
	async holdForSignOut(): Promise<void> {
		const held = this.#entries.filter(
			(entry) => classifyEntry(entry, this.#nowMs()).kind !== 'unreadable'
		);
		if (held.length === 0) return;
		const opIds = held.map((entry) => entry.opId);
		this.#host.opsHeldForSignOut?.(
			held.flatMap((entry) => {
				const verdict = classifyEntry(entry, this.#nowMs());
				return verdict.kind === 'unreadable' ? [] : [verdict.op];
			})
		);
		const ids = new Set(opIds);
		this.#entries = this.#entries.map((entry) =>
			ids.has(entry.opId) ? { ...entry, state: 'signout' } : entry
		);
		this.#mutated();
		await this.#enqueue(() => this.#storage.setStates(opIds, 'signout'));
	}

	/** Releases sign-out holds after an explicit choice; 30-day holds remain. */
	sendAfterSignIn(): void {
		const held = this.#entries.filter((entry) => entry.state === 'signout');
		if (held.length === 0) return;
		const opIds = held.map((entry) => entry.opId);
		const ids = new Set(opIds);
		this.#entries = this.#entries.map((entry) =>
			ids.has(entry.opId) ? { ...entry, state: 'pending' } : entry
		);
		this.#mutated();
		void this.#enqueue(() => this.#storage.setStates(opIds, 'pending'));
		void this.#pump();
	}

	/** Sends the queued ops again, for example after signing in. */
	resume(): void {
		this.#paused = false;
		this.retryNow();
		void this.#pump();
	}

	/** Skips the current retry pause, for example when the connection is back. */
	retryNow(): void {
		this.#wake?.();
	}

	/** Lets the user send held ops now (R10). The ops then go in their usual order. */
	sendHeld(): void {
		const now = this.#nowMs();
		const held = new Set(
			this.#entries
				.filter((entry) => classifyEntry(entry, now).kind === 'held')
				.map((entry) => entry.opId)
		);
		if (held.size === 0) return;
		this.#entries = this.#entries.map((entry) =>
			held.has(entry.opId) ? { ...entry, state: 'approved' } : entry
		);
		this.#mutated();
		for (const opId of held) {
			void this.#enqueue(() => this.#storage.setState(opId, 'approved'));
		}
		void this.#pump();
	}

	/** Drops every waiting op that is not being sent right now (see `discard`). */
	discardAll(): void {
		for (const entry of [...this.#entries]) this.discard(entry.opId);
	}

	/**
	 * Drops a stored op the user does not want (R10, R13). Its promise rejects.
	 * False when the op is being sent right now, or is not stored here.
	 */
	discard(opId: string): boolean {
		if (opId === this.#inFlight) return false;
		const entry = this.#entries.find((item) => item.opId === opId);
		if (!entry) return false;
		const verdict = classifyEntry(entry, this.#nowMs());
		this.#waiters.get(opId)?.reject(new Error('This change was discarded.'));
		this.#waiters.delete(opId);
		this.#removeEntry(opId);
		if (verdict.kind !== 'unreadable') this.#host.opDiscarded(verdict.op);
		void this.#pump();
		return true;
	}

	/** Drops every queued op (their promises reject with `reason`) and stops. */
	dispose(reason: unknown = new Error('This room is closed.')): void {
		this.#disposed = true;
		this.#paused = true;
		for (const entry of this.#entries) this.#waiters.get(entry.opId)?.reject(reason);
		this.#waiters.clear();
		this.#entries = [];
		this.#mutated();
		void this.#enqueue(() => this.#storage.clear());
		this.#wake?.();
	}

	#nowMs(): number {
		return this.#now().getTime();
	}

	/** Runs a storage call after the calls made before it. Never rejects. */
	#enqueue<T>(task: () => Promise<T>): Promise<T> {
		const run = this.#chain.then(task);
		this.#chain = run.then(noop, noop);
		return run;
	}

	/** Re-reads storage until no local change overlapped the read. */
	async #readStored(): Promise<void> {
		for (;;) {
			const version = this.#version;
			const stored = await this.#enqueue(() => this.#storage.read());
			if (version === this.#version) {
				// Sent before a reload: not to be rewritten (see #applyRewrites).
				for (const entry of stored) if (entry.sent === true) this.#sent.add(entry.opId);
				this.#entries = stored;
				this.#publish();
				return;
			}
		}
	}

	#mutated(): void {
		this.#version += 1;
		this.#publish();
	}

	#publish(): void {
		compat.reportWaiting(this, this.#entries.length, this.#storage.durable);
		this.#onChange?.(summarizeEntries(this.#entries, this.#nowMs(), this.#storage.durable));
	}

	#removeEntry(opId: string): void {
		this.#sent.delete(opId);
		this.#entries = this.#entries.filter((entry) => entry.opId !== opId);
		this.#mutated();
		void this.#enqueue(() => this.#storage.remove(opId));
	}

	async #pump(): Promise<void> {
		if (this.#running) return;
		this.#running = true;
		try {
			await withQueueLock(this.#key, () => this.#sendAll(), this.#locks);
		} finally {
			this.#running = false;
		}
		// An op sent while this loop was ending must not wait for the next trigger.
		if (this.#hasSendable()) void this.#pump();
	}

	async #sendAll(): Promise<void> {
		while (!this.#paused && !compat.incompatible) {
			const next = await this.#nextReady();
			if (!next) break;
			await this.#sendOne(next);
		}
	}

	/** The first stored op, if it can go now. Later ops wait behind it. */
	async #nextReady(): Promise<SentOp | null> {
		await this.#readStored();
		const first = this.#entries[0];
		if (!first) return null;
		const verdict = classifyEntry(first, this.#nowMs());
		return verdict.kind === 'ready' ? verdict.op : null;
	}

	#hasSendable(): boolean {
		if (this.#paused || compat.incompatible || this.#entries.length === 0) return false;
		return classifyEntry(this.#entries[0], this.#nowMs()).kind === 'ready';
	}

	/** Makes one request; `#inFlight` is set only while it is open. */
	async #call(op: SentOp): Promise<OpResponse> {
		this.#inFlight = op.op_id;
		try {
			if (!this.#sent.has(op.op_id)) {
				this.#sent.add(op.op_id);
				// Stored before the request goes out: after a reload the server may
				// already have the op, and it is then shown as uncertain.
				await this.#enqueue(() => this.#storage.setSent(op.op_id));
			}
			return await this.#sender.sendOp(this.#slug, op);
		} finally {
			this.#inFlight = null;
		}
	}

	async #sendOne(op: SentOp): Promise<void> {
		let response: OpResponse;
		this.#host.opSending(op);
		try {
			response = await this.#call(op);
		} catch (error) {
			if (this.#disposed) return;
			if (error instanceof ApiError && error.code === INCOMPATIBLE_CODE) {
				// The client refused to send: a new version was seen. Keep the op as
				// it is, with its op_id; the loop stops because `compat` is set.
				this.#host.opUnanswered(op, false);
				return;
			}
			if (isRetryable(error)) {
				this.#host.opUnanswered(op, true);
				// A new version was seen meanwhile: no more retries.
				if (compat.incompatible) return;
				const delay = backoffDelay(this.#delays, this.#attempt);
				this.#attempt += 1;
				await this.#sleep(delay);
				return;
			}
			this.#attempt = 0;
			if (error instanceof ApiError && error.status === 401) {
				this.#paused = true;
				this.#host.opUnanswered(op, false);
				if (this.#host.authRequired(op) === 'stale') this.#paused = false;
				return;
			}
			this.#removeEntry(op.op_id);
			this.#host.opFailed(op, error);
			this.#waiters.get(op.op_id)?.reject(error);
			this.#waiters.delete(op.op_id);
			return;
		}
		if (this.#disposed) return;
		this.#attempt = 0;
		this.#removeEntry(op.op_id);
		// Planned before the host records the answer: `knownSeq` is the seq before it.
		const rewrites = this.#planRewrites(op, response);
		this.#host.opSettled(op, response);
		this.#applyRewrites(rewrites);
		this.#waiters.get(op.op_id)?.resolve(response);
		this.#waiters.delete(op.op_id);
	}

	/**
	 * After an answer, the queued ops that were based on the same view take the
	 * new `base_seq` or uid (R3, R6). Only ops never sent are rewritten.
	 */
	#planRewrites(settled: SentOp, response: OpResponse): Rewrite[] {
		const now = this.#nowMs();
		const later = this.#entries.flatMap((entry) => {
			const verdict = classifyEntry(entry, now);
			return verdict.kind === 'unreadable' ? [] : [verdict.op];
		});
		return planRewrites({
			settled,
			response,
			later,
			sent: (opId) => this.#sent.has(opId),
			knownSeq: (row) => this.#host.knownSeq(row)
		});
	}

	#applyRewrites(rewrites: readonly Rewrite[]): void {
		if (rewrites.length === 0) return;
		const byId = new Map(rewrites.map((rewrite) => [rewrite.opId, rewrite.op]));
		this.#entries = this.#entries.map((entry) => {
			const op = byId.get(entry.opId);
			return op ? { ...entry, op } : entry;
		});
		this.#mutated();
		for (const rewrite of rewrites) {
			void this.#enqueue(() => this.#storage.setOp(rewrite.opId, rewrite.op));
		}
		this.#host.opsRewritten(rewrites);
	}

	#sleep(ms: number): Promise<void> {
		return new Promise((resolve) => {
			const finish = () => {
				clearTimeout(timer);
				this.#wake = null;
				resolve();
			};
			const timer = setTimeout(finish, ms);
			this.#wake = finish;
		});
	}
}
