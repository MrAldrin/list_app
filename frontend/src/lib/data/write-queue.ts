// The write queue of one room. Ops are sent in order, one at a time, each with
// its own retry-safe `op_id` (docs/api.md, "Writing: operations").
//
// - No answer, 502, 503 or 504: retry the same op with the same `op_id`, after
//   a growing pause. Later ops wait, so the order is kept.
// - 401: pause. The ops stay queued; `resume()` after signing in sends them.
// - Any other HTTP error (403, 409, 415, 422, …): that op fails; go on.
// - 200 `applied` or `rejected`: done; go on.

import { isRetryable } from './api';
import { newId } from './ids';
import { ApiError } from './types';
import type { Op, OpResponse, SentOp } from './types';

/** What the queue tells its room. `RoomStore` implements it. */
export interface QueueHost {
	readonly seq: number;
	refresh(): Promise<void>;
	opQueued(op: SentOp): void;
	opSettled(op: SentOp, response: OpResponse): void;
	opFailed(op: SentOp, error: unknown): void;
	authRequired(): void;
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
			while (!this.#paused) {
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
		try {
			response = await this.#sender.sendOp(this.#slug, op);
		} catch (error) {
			if (this.#disposed) return;
			if (isRetryable(error)) {
				const delay = this.#delays[Math.min(this.#attempt, this.#delays.length - 1)];
				this.#attempt += 1;
				await this.#sleep(delay);
				return;
			}
			this.#attempt = 0;
			if (error instanceof ApiError && error.status === 401) {
				this.#paused = true;
				this.#host.authRequired();
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
		// Someone (maybe this op) changed the room: read the changes.
		if (response.seq > this.#host.seq) void this.#host.refresh();
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
