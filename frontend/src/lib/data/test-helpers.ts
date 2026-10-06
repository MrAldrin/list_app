// Shared fakes for the data layer tests. Not used by the app.

import type { EventSourceLike } from './events';
import type { Feed, Item, List, OpResponse, Room, SentOp } from './types';

export const ROOM: Room = { slug: 'home-ab12cd', name: 'Home' };

let counter = 0;
function uid(prefix: string): string {
	counter += 1;
	return `${prefix}-${String(counter).padStart(4, '0')}`;
}

export function makeList(overrides: Partial<List> = {}): List {
	return {
		uid: uid('list'),
		slug: 'groceries-1a2b3c',
		name: 'Groceries',
		tags: [],
		hide_done: { mode: 'off', age_days: 7, recent_count: 10 },
		changed_seq: 1,
		...overrides
	};
}

export function makeItem(listUid: string, overrides: Partial<Item> = {}): Item {
	return {
		uid: uid('item'),
		list_uid: listUid,
		name: 'milk',
		done: false,
		completed_at: null,
		quantity: 1,
		description: '',
		tags: [],
		changed_seq: 1,
		...overrides
	};
}

export function makeFeed(overrides: Partial<Feed> = {}): Feed {
	return {
		seq: 1,
		full: false,
		room: ROOM,
		lists: [],
		items: [],
		deletions: [],
		...overrides
	};
}

export function applied(op: SentOp, seq: number, result: Record<string, unknown> = {}): OpResponse {
	return { op_id: op.op_id, status: 'applied', result, seq };
}

export interface Deferred<T> {
	promise: Promise<T>;
	resolve: (value: T) => void;
	reject: (error: unknown) => void;
}

export function deferred<T>(): Deferred<T> {
	let resolve!: (value: T) => void;
	let reject!: (error: unknown) => void;
	const promise = new Promise<T>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

/** Lets pending promise callbacks run. */
export async function settle(rounds = 40): Promise<void> {
	for (let round = 0; round < rounds; round += 1) await Promise.resolve();
}

/** A fake `EventSource`: tests fire its events by hand. */
export class FakeEventSource implements EventSourceLike {
	static instances: FakeEventSource[] = [];

	readonly url: string;
	readyState = 0;
	closed = false;
	#listeners = new Map<string, ((event: Event) => void)[]>();

	constructor(url: string) {
		this.url = url;
		FakeEventSource.instances.push(this);
	}

	static get last(): FakeEventSource {
		return FakeEventSource.instances[FakeEventSource.instances.length - 1];
	}

	static reset(): void {
		FakeEventSource.instances = [];
	}

	addEventListener(type: string, listener: (event: Event) => void): void {
		this.#listeners.set(type, [...(this.#listeners.get(type) ?? []), listener]);
	}

	close(): void {
		this.closed = true;
		this.readyState = 2;
	}

	open(): void {
		this.readyState = 1;
		this.#fire('open', new Event('open'));
	}

	seq(seq: number): void {
		this.#fire('seq', new MessageEvent('seq', { data: JSON.stringify({ seq }) }));
	}

	revoked(): void {
		this.#fire('revoked', new MessageEvent('revoked', { data: '{}' }));
	}

	/** A dropped connection: `reconnecting` true means the browser retries itself. */
	fail(reconnecting: boolean): void {
		this.readyState = reconnecting ? 0 : 2;
		this.#fire('error', new Event('error'));
	}

	#fire(type: string, event: Event): void {
		for (const listener of this.#listeners.get(type) ?? []) listener(event);
	}
}

/** A fake visibility target for the live-updates `visibilitychange` handling. */
export class FakeVisibility {
	visibilityState: DocumentVisibilityState = 'visible';
	#listeners: (() => void)[] = [];

	addEventListener(_type: string, listener: () => void): void {
		this.#listeners.push(listener);
	}

	removeEventListener(_type: string, listener: () => void): void {
		this.#listeners = this.#listeners.filter((existing) => existing !== listener);
	}

	set(state: DocumentVisibilityState): void {
		this.visibilityState = state;
		for (const listener of this.#listeners) listener();
	}
}
