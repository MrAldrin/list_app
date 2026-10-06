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

/**
 * The stream's state: `connecting` until the first open, `open`, then
 * `reconnecting` while it is down (the browser or we try again), `stopped`
 * when not running (also after access was revoked).
 */
export type LiveState = 'stopped' | 'connecting' | 'open' | 'reconnecting';

/** What the stream updates. `RoomStore` implements it. */
export interface LiveHost {
	readonly seq: number;
	/** True while the last read failed: the next `seq` event reads again even if equal. */
	readonly stale?: boolean;
	refresh(): Promise<void | boolean>;
	authRequired(): void;
	/** Hears each change of the stream's state, for a connection indicator. */
	liveChanged?(state: LiveState): void;
}

type VisibilityTarget = Pick<
	Document,
	'visibilityState' | 'addEventListener' | 'removeEventListener'
>;
type ConnectivityTarget = Pick<Window, 'addEventListener' | 'removeEventListener'>;

export interface LiveUpdatesOptions {
	url: string;
	host: LiveHost;
	/** Asks the server whether we are still signed in (`GET …/session`). */
	checkSession: () => Promise<SessionState>;
	/** Revalidates access and refreshes before allowing queued retries. */
	onReconnect?: () => Promise<boolean> | boolean;
	createEventSource?: EventSourceFactory;
	reconnectDelays?: readonly number[];
	/** Where to listen for the page becoming visible; null to skip. */
	visibility?: VisibilityTarget | null;
	/** Revalidate on the browser's online signal; the signal itself grants no access. */
	connectivity?: ConnectivityTarget | null;
}

export const RECONNECT_DELAYS = [1_000, 2_000, 5_000, 10_000, 30_000];

/**
 * A page hidden this long gets a new stream when it shows again. Phones may
 * cut a hidden page's connection without an error, and keep-alives are
 * comments, which `EventSource` does not report, so we cannot tell.
 */
export const STALE_AFTER_HIDDEN = 30_000;

export class LiveUpdates {
	readonly #options: LiveUpdatesOptions;
	readonly #create: EventSourceFactory;
	readonly #delays: readonly number[];
	readonly #visibility: VisibilityTarget | null;
	readonly #connectivity: ConnectivityTarget | null;

	#source: EventSourceLike | null = null;
	#running = false;
	#hasOpened = false;
	#attempt = 0;
	#timer: ReturnType<typeof setTimeout> | null = null;
	#state: LiveState = 'stopped';
	#hiddenAt: number | null = null;

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
		this.#connectivity =
			options.connectivity !== undefined
				? options.connectivity
				: typeof window === 'undefined'
					? null
					: window;
	}

	get running(): boolean {
		return this.#running;
	}

	get state(): LiveState {
		return this.#state;
	}

	start(): void {
		if (this.#running) return;
		this.#running = true;
		this.#hasOpened = false;
		this.#attempt = 0;
		this.#hiddenAt = null;
		this.#setState('connecting');
		this.#visibility?.addEventListener('visibilitychange', this.#onVisibilityChange);
		this.#connectivity?.addEventListener('online', this.#onOnline);
		this.#connectivity?.addEventListener('offline', this.#onOffline);
		this.#connect();
	}

	stop(): void {
		this.#running = false;
		this.#visibility?.removeEventListener('visibilitychange', this.#onVisibilityChange);
		this.#connectivity?.removeEventListener('online', this.#onOnline);
		this.#connectivity?.removeEventListener('offline', this.#onOffline);
		this.#clearTimer();
		this.#source?.close();
		this.#source = null;
		this.#setState('stopped');
	}

	#setState(state: LiveState): void {
		if (state === this.#state) return;
		this.#state = state;
		this.#options.host.liveChanged?.(state);
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
			this.#setState('open');
			// The first open is followed by a `seq` event. After a drop we may have
			// missed changes, so read them now.
			if (this.#hasOpened) this.#reconnected();
			this.#hasOpened = true;
		});
		source.addEventListener('seq', (event) => {
			if (!current()) return;
			const seq = readSeq(event);
			// A lower seq means the database was restored: the feed then sends a full snapshot.
			const { host } = this.#options;
			if (seq !== null && (seq !== host.seq || host.stale)) void host.refresh();
		});
		source.addEventListener('revoked', () => {
			if (!current()) return;
			void this.#closed();
		});
		source.addEventListener('error', () => {
			if (!current()) return;
			this.#setState('reconnecting');
			// While connecting, the browser retries by itself. Closed means it gave up
			// (for example a 401 answer), so we decide.
			if (source.readyState === CLOSED) void this.#closed();
		});
	}

	async #closed(): Promise<void> {
		this.#source?.close();
		this.#source = null;
		this.#setState('reconnecting');
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
		if (!this.#options.onReconnect) {
			void this.#options.host.refresh();
			return;
		}
		const validated = this.#options.onReconnect();
		if (validated === undefined) void this.#options.host.refresh();
	}

	#onOffline = () => {
		if (this.#running) this.#setState('reconnecting');
	};

	#onOnline = () => {
		if (!this.#running) return;
		if (!this.#source || this.#source.readyState === CLOSED) {
			this.#setState('reconnecting');
			this.#connect();
		}
		this.#reconnected();
	};

	// Phones pause hidden pages and may drop the stream without telling us.
	#onVisibilityChange = () => {
		if (!this.#running) return;
		if (this.#visibility?.visibilityState !== 'visible') {
			this.#hiddenAt ??= Date.now();
			return;
		}
		const hiddenFor = this.#hiddenAt === null ? 0 : Date.now() - this.#hiddenAt;
		this.#hiddenAt = null;
		if (!this.#source || this.#source.readyState === CLOSED || hiddenFor >= STALE_AFTER_HIDDEN) {
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
