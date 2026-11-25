import { Schema } from 'effect';
import type { EventFrame } from '#lib/contracts/v1/feed.ts';
import { ApiError, apiError } from './api';

const MAX_STREAMS = 100;
const RECHECK_MS = 15_000;
// Keep the connection active even with Bun's default 10-second idle timeout.
const PING_MS = 5_000;
const encoder = new TextEncoder();

type Cursor = { roomId: number; seq: number };
type ReadCursor = (signal: AbortSignal) => Promise<Cursor>;
type Frame = typeof EventFrame.Type;

const active = new Set<{ roomId?: number; wake: () => void; close: () => void }>();
let shuttingDown = false;

export function wakeRoomStreams(roomId: number): void {
	for (const stream of active) if (stream.roomId === roomId) stream.wake();
}

export function stopLiveStreams(): void {
	shuttingDown = true;
	for (const stream of active) stream.close();
}

export function liveStream(
	contract: { status: number; response: Schema.Schema<Frame> },
	request: Request,
	read: ReadCursor
): Promise<Response> {
	// SvelteKit can call GET for HEAD. A body the caller will never read must
	// not reserve a stream.
	if (request.method !== 'GET') throw apiError(405, 'invalid_request', undefined, { Allow: 'GET' });
	if (shuttingDown || active.size >= MAX_STREAMS) throw apiError(503, 'unavailable');

	const encodeFrame = Schema.encodeSync(contract.response);
	const abort = new AbortController();
	let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
	let wakeWait: (() => void) | undefined;
	let dirty = true;
	let lastSeq: number | undefined;
	let checkedAt = -Infinity;
	let sentAt = -Infinity;

	const stream = {
		roomId: undefined as number | undefined,
		wake() {
			dirty = true;
			wakeWait?.();
		},
		close() {
			if (!release()) return;
			controller?.close();
		}
	};

	function release(): boolean {
		if (!active.delete(stream)) return false;
		request.signal.removeEventListener('abort', stream.close);
		abort.abort();
		wakeWait?.();
		return true;
	}

	function frame(output: ReadableStreamDefaultController<Uint8Array>, value: Frame): void {
		const encoded = encodeFrame(value);
		const line =
			'comment' in encoded
				? `:${encoded.comment}\n\n`
				: `event: ${encoded.event}\ndata: ${JSON.stringify(encoded.data)}\n\n`;
		output.enqueue(encoder.encode(line));
		sentAt = performance.now();
	}

	function wait(ms: number): Promise<void> {
		return new Promise((resolve) => {
			const timer = setTimeout(finish, ms);
			wakeWait = finish;
			function finish() {
				clearTimeout(timer);
				wakeWait = undefined;
				resolve();
			}
		});
	}

	async function pull(output: ReadableStreamDefaultController<Uint8Array>): Promise<void> {
		try {
			while (active.has(stream)) {
				const now = performance.now();
				if (dirty || now >= checkedAt + RECHECK_MS) {
					dirty = false;
					checkedAt = now;
					const { roomId, seq } = await read(abort.signal);
					if (!active.has(stream)) return;
					if (roomId !== stream.roomId) throw apiError(401, 'not_authenticated');
					if (seq !== lastSeq) {
						lastSeq = seq;
						frame(output, { event: 'seq', data: { seq } });
						return;
					}
				}
				if (performance.now() >= sentAt + PING_MS) {
					frame(output, { comment: 'ping' });
					return;
				}
				if (!dirty)
					await wait(Math.min(checkedAt + RECHECK_MS, sentAt + PING_MS) - performance.now());
			}
		} catch (error) {
			if (!active.has(stream)) return;
			if (error instanceof ApiError && error.status === 401)
				frame(output, { event: 'revoked', data: {} });
			else if (!(error instanceof ApiError && error.status === 503))
				console.error('Unexpected error in live cursor check');
			stream.close();
		}
	}

	// Reserve before checking access. A failed admission also returns its slot.
	active.add(stream);
	request.signal.addEventListener('abort', stream.close, { once: true });
	if (request.signal.aborted) stream.close();
	return (async () => {
		try {
			stream.roomId = (await read(abort.signal)).roomId;
			if (!active.has(stream)) throw apiError(503, 'unavailable');
			// The first pull reads again, after subscription, so no committed write
			// can fall between admission and the first cursor. Pull gives us
			// backpressure: a slow client does not build an unbounded event queue.
			return new Response(
				new ReadableStream<Uint8Array>({
					start(output) {
						controller = output;
					},
					pull,
					cancel() {
						release();
					}
				}),
				{
					status: contract.status,
					headers: { 'Content-Type': 'text/event-stream', 'X-Accel-Buffering': 'no' }
				}
			);
		} catch (error) {
			if (!release()) throw apiError(503, 'unavailable');
			throw error;
		}
	})();
}
