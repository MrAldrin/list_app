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
//
// The host hears when an op goes out and when it comes back, so the room can
// hold back changes feeds while an answer is open (see RoomStore).

import { isRetryable } from './api';
import { compat, INCOMPATIBLE_CODE } from './compat.svelte';
import { newId } from './ids';
import { ApiError } from './types';
import type { Op, OpResponse, SentOp } from './types';

/** What the queue tells its room. `RoomStore` implements it. */
export interface QueueHost {
	opQueued(op: SentOp): void;
	/** The op is on its way; its answer is open. */
	opSending(op: SentOp): void;
	/** The answer is applied or rejected; the host reads the changes it needs. */
	opSettled(op: SentOp, response: OpResponse): void;
	/** The op failed for good (HTTP error); it is dropped. */
	opFailed(op: SentOp, error: unknown): void;
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

/**
 * Where queued ops live until the server answers. In memory for now;
 * Milestone 6 keeps them in IndexedDB behind this same interface.
 */
export interface QueueStorage {
	all(): readonly SentOp[];
	add(op: SentOp): void;
	remove(opId: string): void;
	clear(): void;
}

export class MemoryQueueStorage implements QueueStorage {
	#ops: SentOp[] = [];

	all(): readonly SentOp[] {
		return this.#ops;
	}
	add(op: SentOp): void {
		this.#ops.push(op);
	}
	remove(opId: string): void {
		this.#ops = this.#ops.filter((op) => op.op_id !== opId);
	}
	clear(): void {
		this.#ops = [];
	}
}

/** Pauses before each retry, in milliseconds; the last one repeats. */
export const RETRY_DELAYS = [1_000, 2_000, 5_000, 10_000, 30_000];

export interface WriteQueueOptions {
	storage?: QueueStorage;
	retryDelays?: readonly number[];
}

interface Waiter {
	resolve: (response: OpResponse) => void;
	reject: (error: unknown) => void;
}

export class WriteQueue {
	readonly #slug: string;
	readonly #sender: OpSender;
	readonly #host: QueueHost;
	readonly #storage: QueueStorage;
	readonly #delays: readonly number[];
	readonly #waiters = new Map<string, Waiter>();

	#running = false;
	#paused = false;
	#disposed = false;
	#attempt = 0;
	#wake: (() => void) | null = null;

	constructor(slug: string, sender: OpSender, host: QueueHost, options: WriteQueueOptions = {}) {
		this.#slug = slug;
		this.#sender = sender;
		this.#host = host;
		this.#storage = options.storage ?? new MemoryQueueStorage();
		this.#delays = options.retryDelays ?? RETRY_DELAYS;
	}

	/** Ops not answered yet, oldest first. */
	get pending(): readonly SentOp[] {
		return this.#storage.all();
	}

	/** True after a 401, until `resume()`. */
	get paused(): boolean {
		return this.#paused;
	}

	/**
	 * Queues one op with a new `op_id`. Resolves with the server's answer
	 * (`applied` or `rejected`); rejects with the `ApiError` if the op failed.
	 */
	send(op: Op): Promise<OpResponse> {
		if (this.#disposed) return Promise.reject(new Error('This room is closed.'));
		const sent = { ...op, op_id: newId() } as SentOp;
		const promise = new Promise<OpResponse>((resolve, reject) => {
			this.#waiters.set(sent.op_id, { resolve, reject });
		});
		this.#storage.add(sent);
		this.#host.opQueued(sent);
		void this.#pump();
		return promise;
	}

	/** Stops future sends while retaining pending ops and their original op_ids. */
	pause(): void {
		this.#paused = true;
		this.#wake?.();
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

	/** Drops every queued op (their promises reject with `reason`) and stops. */
	dispose(reason: unknown = new Error('This room is closed.')): void {
		this.#disposed = true;
		this.#paused = true;
		for (const op of this.#storage.all()) this.#waiters.get(op.op_id)?.reject(reason);
		this.#waiters.clear();
		this.#storage.clear();
		this.#wake?.();
	}

	async #pump(): Promise<void> {
		if (this.#running) return;
		this.#running = true;
		try {
			while (!this.#paused && !compat.incompatible) {
				const op = this.#storage.all()[0];
				if (!op) break;
				await this.#sendOne(op);
			}
		} finally {
			this.#running = false;
		}
	}

	async #sendOne(op: SentOp): Promise<void> {
		let response: OpResponse;
		this.#host.opSending(op);
		try {
			response = await this.#sender.sendOp(this.#slug, op);
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
				const delay = this.#delays[Math.min(this.#attempt, this.#delays.length - 1)];
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
			this.#finish(op);
			this.#host.opFailed(op, error);
			this.#waiters.get(op.op_id)?.reject(error);
			this.#waiters.delete(op.op_id);
			return;
		}
		if (this.#disposed) return;
		this.#attempt = 0;
		this.#finish(op);
		this.#host.opSettled(op, response);
		this.#waiters.get(op.op_id)?.resolve(response);
		this.#waiters.delete(op.op_id);
	}

	#finish(op: SentOp): void {
		this.#storage.remove(op.op_id);
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
