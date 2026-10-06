// A thin client for the JSON API (docs/api.md). Only the data layer uses it;
// components never call `fetch` themselves.

import { ApiError, NetworkError } from './types';
import type {
	Feed,
	Invitation,
	IssuedInvitation,
	OpResponse,
	Room,
	SentOp,
	ShareLink
} from './types';

/** The API sits at the origin root. */
export const API_BASE = '/api/v1';

const ADMIN = `${API_BASE}/admin`;

export type FetchFn = typeof fetch;

function roomPath(slug: string, rest: string): string {
	return `${API_BASE}/rooms/${encodeURIComponent(slug)}/${rest}`;
}

function sharePath(token: string, rest: string): string {
	return `${API_BASE}/share/${encodeURIComponent(token)}/${rest}`;
}

function invitationPath(token: string, rest = ''): string {
	return `${API_BASE}/invitations/${encodeURIComponent(token)}${rest}`;
}

function shareLinkPath(slug: string, listUid: string): string {
	return roomPath(slug, `lists/${encodeURIComponent(listUid)}/share-link`);
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

	/** Changes the room password. The answer sets a new room cookie; other devices are signed out. */
	changePassword(slug: string, currentPassword: string, newPassword: string): Promise<Room> {
		return this.request<{ room: Room }>('POST', roomPath(slug, 'password'), {
			current_password: currentPassword,
			new_password: newPassword
		}).then((data) => data.room);
	}

	/** Deletes the room with all its lists and items. */
	deleteRoom(slug: string, password: string): Promise<void> {
		return this.request<void>('DELETE', `${API_BASE}/rooms/${encodeURIComponent(slug)}`, {
			password
		});
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

	// Admin (APP_PASSWORD): never gives room access.

	adminLogin(password: string): Promise<void> {
		return this.request<void>('POST', `${ADMIN}/session`, { password }).then(() => undefined);
	}

	/** Resolves when signed in as admin; `ApiError` 401 `admin_required` when not. */
	adminSession(): Promise<void> {
		return this.request<void>('GET', `${ADMIN}/session`).then(() => undefined);
	}

	adminLogout(): Promise<void> {
		return this.request<void>('DELETE', `${ADMIN}/session`);
	}

	/** Every room, by name ignoring case. */
	adminRooms(): Promise<Room[]> {
		return this.request<{ rooms: Room[] }>('GET', `${ADMIN}/rooms`).then((data) => data.rooms);
	}

	adminCreateRoom(name: string, password: string): Promise<Room> {
		return this.request<{ room: Room }>('POST', `${ADMIN}/rooms`, { name, password }).then(
			(data) => data.room
		);
	}

	/** Sets a new room password; every device of the room must sign in again. */
	adminResetPassword(slug: string, newPassword: string): Promise<void> {
		return this.request<void>('POST', `${ADMIN}/rooms/${encodeURIComponent(slug)}/password`, {
			new_password: newPassword
		}).then(() => undefined);
	}

	/** Every kept invitation, newest first. */
	adminInvitations(): Promise<Invitation[]> {
		return this.request<{ invitations: Invitation[] }>('GET', `${ADMIN}/invitations`).then(
			(data) => data.invitations
		);
	}

	/** A new 7-day invitation. Its token is never sent again. */
	adminIssueInvitation(): Promise<IssuedInvitation> {
		return this.request<IssuedInvitation>('POST', `${ADMIN}/invitations`, {});
	}

	adminRevokeInvitation(id: number): Promise<void> {
		return this.request<void>('POST', `${ADMIN}/invitations/${id}/revoke`, {}).then(
			() => undefined
		);
	}

	// Creation invitations (anyone with the link): no sign-in.

	/** Resolves when the link can create a room; `ApiError` 404 `invitation_unavailable` when not. */
	checkInvitation(token: string): Promise<void> {
		return this.request<void>('GET', invitationPath(token)).then(() => undefined);
	}

	/** Creates a room. The creator is not signed in to it. */
	createRoomFromInvitation(token: string, name: string, password: string): Promise<Room> {
		return this.request<{ room: Room }>('POST', invitationPath(token, '/rooms'), {
			name,
			password
		}).then((data) => data.room);
	}

	// Share links (room members): the token for `/share/{token}`.

	shareLink(slug: string, listUid: string): Promise<ShareLink> {
		return this.request<ShareLink>('GET', shareLinkPath(slug, listUid));
	}

	/** Gives the list a new share token; the old link stops working for everyone. */
	resetShareLink(slug: string, listUid: string): Promise<ShareLink> {
		return this.request<ShareLink>('POST', shareLinkPath(slug, listUid), {});
	}

	// A share link's own reads and writes: one list, by its token.

	shareChanges(token: string, since: number): Promise<Feed> {
		return this.request<Feed>('GET', sharePath(token, `changes?since=${since}`));
	}

	sendShareOp(token: string, op: SentOp): Promise<OpResponse> {
		return this.request<OpResponse>('POST', sharePath(token, 'ops'), op);
	}

	shareEventsUrl(token: string): string {
		return sharePath(token, 'events');
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
