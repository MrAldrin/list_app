import { describe, expect, it, vi } from 'vitest';
import { Api, isRetryable } from './api';
import { ApiError, NetworkError } from './types';
import type { SentOp } from './types';

function json(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

function fakeFetch(response: Response | Error) {
	return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		void input;
		void init;
		if (response instanceof Error) throw response;
		return response;
	});
}

describe('Api', () => {
	it('reads the changes feed from /api/v1 at the origin root', async () => {
		const feed = { seq: 3, full: true, room: {}, lists: [], items: [], deletions: [] };
		const fetch = fakeFetch(json(200, feed));
		const result = await new Api(fetch).changes('home ab', 2);

		expect(result).toEqual(feed);
		const [url, init] = fetch.mock.calls[0];
		expect(url).toBe('/api/v1/rooms/home%20ab/changes?since=2');
		expect(init).toMatchObject({ method: 'GET', credentials: 'same-origin' });
		expect(init?.body).toBeUndefined();
	});

	it('posts ops as JSON', async () => {
		const op: SentOp = { op_id: 'x', type: 'list.delete', list_uid: 'l' };
		const answer = { op_id: 'x', status: 'applied', result: {}, seq: 4 };
		const fetch = fakeFetch(json(200, answer));

		expect(await new Api(fetch).sendOp('home', op)).toEqual(answer);
		const [url, init] = fetch.mock.calls[0];
		expect(url).toBe('/api/v1/rooms/home/ops');
		expect(init?.method).toBe('POST');
		expect((init?.headers as Record<string, string>)['Content-Type']).toBe('application/json');
		expect(JSON.parse(init?.body as string)).toEqual(op);
	});

	it('maps the error format to ApiError', async () => {
		const fetch = fakeFetch(
			json(401, { error: { code: 'not_authenticated', message: 'Sign in to this room.' } })
		);
		const error = await new Api(fetch).whoAmI('home').catch((caught) => caught);

		expect(error).toBeInstanceOf(ApiError);
		expect(error).toMatchObject({
			status: 401,
			code: 'not_authenticated',
			message: 'Sign in to this room.'
		});
		expect(isRetryable(error)).toBe(false);
	});

	it('treats a non-JSON gateway error as unavailable and retryable', async () => {
		const fetch = fakeFetch(new Response('<html>Bad gateway</html>', { status: 502 }));
		const error = await new Api(fetch).lastRoom().catch((caught) => caught);

		expect(error).toMatchObject({ status: 502, code: 'unavailable' });
		expect(isRetryable(error)).toBe(true);
	});

	it('turns a failed fetch into NetworkError', async () => {
		const fetch = fakeFetch(new TypeError('Failed to fetch'));
		const error = await new Api(fetch).changes('home', 0).catch((caught) => caught);

		expect(error).toBeInstanceOf(NetworkError);
		expect(isRetryable(error)).toBe(true);
	});

	it('marks only 503-style errors as retryable', () => {
		expect(isRetryable(new ApiError(503, 'unavailable', ''))).toBe(true);
		expect(isRetryable(new ApiError(500, 'internal_error', ''))).toBe(false);
		expect(isRetryable(new ApiError(422, 'invalid_request', ''))).toBe(false);
	});

	it('has the session calls', async () => {
		const room = { slug: 'home', name: 'Home' };
		const login = fakeFetch(json(200, { room }));
		expect(await new Api(login).login('home', 'secret')).toEqual(room);
		expect(login.mock.calls[0][0]).toBe('/api/v1/rooms/home/session');
		expect(JSON.parse(login.mock.calls[0][1]?.body as string)).toEqual({ password: 'secret' });

		const logout = fakeFetch(new Response(null, { status: 204 }));
		await expect(new Api(logout).logout('home')).resolves.toBeUndefined();
		expect(logout.mock.calls[0][1]?.method).toBe('DELETE');

		const last = fakeFetch(json(200, { slug: null }));
		expect(await new Api(last).lastRoom()).toBeNull();
		expect(last.mock.calls[0][0]).toBe('/api/v1/last-room');
	});

	it('has the room management calls', async () => {
		const room = { slug: 'home', name: 'Home' };
		const change = fakeFetch(json(200, { room }));
		expect(await new Api(change).changePassword('home', 'old', 'new')).toEqual(room);
		expect(change.mock.calls[0][0]).toBe('/api/v1/rooms/home/password');
		expect(change.mock.calls[0][1]?.method).toBe('POST');
		expect(JSON.parse(change.mock.calls[0][1]?.body as string)).toEqual({
			current_password: 'old',
			new_password: 'new'
		});

		const remove = fakeFetch(new Response(null, { status: 204 }));
		await expect(new Api(remove).deleteRoom('home', 'secret')).resolves.toBeUndefined();
		expect(remove.mock.calls[0][0]).toBe('/api/v1/rooms/home');
		expect(remove.mock.calls[0][1]?.method).toBe('DELETE');
		expect(JSON.parse(remove.mock.calls[0][1]?.body as string)).toEqual({ password: 'secret' });

		const wrong = fakeFetch(
			json(403, { error: { code: 'wrong_password', message: 'Incorrect password' } })
		);
		await expect(new Api(wrong).deleteRoom('home', 'bad')).rejects.toMatchObject({
			status: 403,
			code: 'wrong_password',
			message: 'Incorrect password'
		});
	});

	it('builds the events URL', () => {
		expect(new Api(fakeFetch(json(200, {}))).eventsUrl('home')).toBe('/api/v1/rooms/home/events');
	});
});
