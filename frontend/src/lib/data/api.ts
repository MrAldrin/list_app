// A thin client for the JSON API (docs/api.md). Only the data layer uses it;
// components never call `fetch` themselves.

import { ApiError, NetworkError } from './types';
import type { Feed, OpResponse, Room, SentOp } from './types';

/** The API sits at the origin root, not under the app's `/app` base path. */
export const API_BASE = '/api/v1';

export type FetchFn = typeof fetch;

function roomPath(slug: string, rest: string): string {
	return `${API_BASE}/rooms/${encodeURIComponent(slug)}/${rest}`;
}

/** Statuses worth retrying later with the same request: the server is down or busy. */
export function isRetryable(error: unknown): boolean {
	if (error instanceof NetworkError) return true;
	return error instanceof ApiError && [502, 503, 504].includes(error.status);
}

export class Api {
	readonly #fetch: FetchFn;

	constructor(fetchFn?: FetchFn) {
		// Bound lazily: calling a detached `window.fetch` throws "Illegal invocation".
		this.#fetch = fetchFn ?? ((input, init) => globalThis.fetch(input, init));
	}

	/** Sends one request. Throws `NetworkError` without an answer, `ApiError` for HTTP errors. */
	async request<T>(method: string, path: string, body?: unknown): Promise<T> {
		const headers: Record<string, string> = { Accept: 'application/json' };
		const init: RequestInit = { method, headers, credentials: 'same-origin' };
		if (body !== undefined) {
			headers['Content-Type'] = 'application/json';
			init.body = JSON.stringify(body);
		}

		let response: Response;
		try {
			response = await this.#fetch(path, init);
		} catch (error) {
			if (error instanceof DOMException && error.name === 'AbortError') throw error;
			throw new NetworkError();
		}

		if (response.status === 204) return undefined as T;

		let data: unknown;
		try {
			data = await response.json();
		} catch {
			data = undefined;
		}

		if (!response.ok) throw toApiError(response.status, data);
		if (data === undefined) {
			throw new ApiError(
				response.status,
				'internal_error',
				'The server sent an unreadable answer.'
			);
		}
		return data as T;
	}

	login(slug: string, password: string): Promise<Room> {
		return this.request<{ room: Room }>('POST', roomPath(slug, 'session'), { password }).then(
			(data) => data.room
		);
	}

	/** "Who am I": the room, or `ApiError` 401 when not signed in. */
	whoAmI(slug: string): Promise<Room> {
		return this.request<{ room: Room }>('GET', roomPath(slug, 'session')).then((data) => data.room);
	}

	logout(slug: string): Promise<void> {
		return this.request<void>('DELETE', roomPath(slug, 'session'));
	}

	/** The slug of the last room this browser signed in to, or null. */
	lastRoom(): Promise<string | null> {
		return this.request<{ slug: string | null }>('GET', `${API_BASE}/last-room`).then(
			(data) => data.slug
		);
	}

	changes(slug: string, since: number): Promise<Feed> {
		return this.request<Feed>('GET', roomPath(slug, `changes?since=${since}`));
	}

	sendOp(slug: string, op: SentOp): Promise<OpResponse> {
		return this.request<OpResponse>('POST', roomPath(slug, 'ops'), op);
	}

	eventsUrl(slug: string): string {
		return roomPath(slug, 'events');
	}
}

function toApiError(status: number, data: unknown): ApiError {
	const error = (data as { error?: { code?: unknown; message?: unknown } } | undefined)?.error;
	if (error && typeof error.code === 'string' && typeof error.message === 'string') {
		return new ApiError(status, error.code, error.message);
	}
	// Not our JSON shape, for example a proxy's error page during a deploy.
	if (status >= 500) {
		return new ApiError(status, 'unavailable', 'The server is busy. Please try again.');
	}
	return new ApiError(status, 'invalid_request', 'This request is not valid.');
}

/** The shared client used by the app. Tests make their own with a fake fetch. */
export const api = new Api();
