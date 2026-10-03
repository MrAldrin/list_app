// Live updates: the room's Server-Sent Events stream (docs/api.md, "Live updates").
// The stream only says "the room seq is now N"; the room store then reads the
// changes feed.

/** The part of the browser's `EventSource` we use; tests pass a fake. */
export interface EventSourceLike {
	readonly readyState: number;
	addEventListener(type: string, listener: (event: Event) => void): void;
	close(): void;
}

export type EventSourceFactory = (url: string) => EventSourceLike;

/** `EventSource.CLOSED`: the browser gave up and will not reconnect by itself. */
const CLOSED = 2;

export type SessionState = 'signed_in' | 'signed_out' | 'unknown';

/** What the stream updates. `RoomStore` implements it. */
export interface LiveHost {
	readonly seq: number;
	refresh(): Promise<void>;
	authRequired(): void;
}

type VisibilityTarget = Pick<
	Document,
	'visibilityState' | 'addEventListener' | 'removeEventListener'
>;

export interface LiveUpdatesOptions {
	url: string;
	host: LiveHost;
	/** Asks the server whether we are still signed in (`GET …/session`). */
	checkSession: () => Promise<SessionState>;
	/** Called when the connection is back, for example to retry queued writes now. */
	onReconnect?: () => void;
	createEventSource?: EventSourceFactory;
	reconnectDelays?: readonly number[];
	/** Where to listen for the page becoming visible; null to skip. */
	visibility?: VisibilityTarget | null;
}

export const RECONNECT_DELAYS = [1_000, 2_000, 5_000, 10_000, 30_000];

export class LiveUpdates {
	readonly #options: LiveUpdatesOptions;
	readonly #create: EventSourceFactory;
	readonly #delays: readonly number[];
	readonly #visibility: VisibilityTarget | null;

	#source: EventSourceLike | null = null;
	#running = false;
	#hasOpened = false;
	#attempt = 0;
	#timer: ReturnType<typeof setTimeout> | null = null;

	constructor(options: LiveUpdatesOptions) {
		this.#options = options;
		this.#create = options.createEventSource ?? ((url) => new EventSource(url));
		this.#delays = options.reconnectDelays ?? RECONNECT_DELAYS;
		this.#visibility =
			options.visibility !== undefined
				? options.visibility
				: typeof document === 'undefined'
					? null
					: document;
	}

	get running(): boolean {
		return this.#running;
	}

	start(): void {
		if (this.#running) return;
		this.#running = true;
		this.#hasOpened = false;
		this.#attempt = 0;
		this.#visibility?.addEventListener('visibilitychange', this.#onVisibilityChange);
		this.#connect();
	}

	stop(): void {
		this.#running = false;
		this.#visibility?.removeEventListener('visibilitychange', this.#onVisibilityChange);
		this.#clearTimer();
		this.#source?.close();
		this.#source = null;
	}

	#connect(): void {
		this.#clearTimer();
		this.#source?.close();
		const source = this.#create(this.#options.url);
		this.#source = source;
		const current = () => this.#running && this.#source === source;

		source.addEventListener('open', () => {
			if (!current()) return;
			this.#attempt = 0;
			// The first open is followed by a `seq` event. After a drop we may have
			// missed changes, so read them now.
			if (this.#hasOpened) this.#reconnected();
			this.#hasOpened = true;
		});
		source.addEventListener('seq', (event) => {
			if (!current()) return;
			const seq = readSeq(event);
			// A lower seq means the database was restored: the feed then sends a full snapshot.
			if (seq !== null && seq !== this.#options.host.seq) void this.#options.host.refresh();
		});
		source.addEventListener('revoked', () => {
			if (!current()) return;
			void this.#closed();
		});
		source.addEventListener('error', () => {
			if (!current()) return;
			// While connecting, the browser retries by itself. Closed means it gave up
			// (for example a 401 answer), so we decide.
			if (source.readyState === CLOSED) void this.#closed();
		});
	}

	async #closed(): Promise<void> {
		this.#source?.close();
		this.#source = null;
		const session = await this.#options.checkSession().catch((): SessionState => 'unknown');
		if (!this.#running || this.#source) return;
		if (session === 'signed_out') {
			this.stop();
			this.#options.host.authRequired();
			return;
		}
		const delay = this.#delays[Math.min(this.#attempt, this.#delays.length - 1)];
		this.#attempt += 1;
		this.#timer = setTimeout(() => {
			this.#timer = null;
			if (this.#running) this.#connect();
		}, delay);
	}

	#reconnected(): void {
		void this.#options.host.refresh();
		this.#options.onReconnect?.();
	}

	// Phones pause hidden pages and may drop the stream without telling us.
	#onVisibilityChange = () => {
		if (!this.#running || this.#visibility?.visibilityState !== 'visible') return;
		if (!this.#source || this.#source.readyState === CLOSED) {
			this.#attempt = 0;
			this.#connect();
		}
		this.#reconnected();
	};

	#clearTimer(): void {
		if (this.#timer !== null) clearTimeout(this.#timer);
		this.#timer = null;
	}
}

function readSeq(event: Event): number | null {
	try {
		const seq = JSON.parse((event as MessageEvent).data).seq;
		return Number.isInteger(seq) ? seq : null;
	} catch {
		return null;
	}
}
