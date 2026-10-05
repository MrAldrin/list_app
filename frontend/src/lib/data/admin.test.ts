import { describe, expect, it, vi } from 'vitest';
import * as admin from './admin';
import { Api } from './api';

function json(status: number, body: unknown): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

function error(status: number, code: string, message: string): Response {
	return json(status, { error: { code, message } });
}

/** A fake fetch that answers each call with the next response. */
function fakeFetch(...responses: (Response | Error)[]) {
	return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		void input;
		void init;
		const next = responses.shift();
		if (!next) throw new Error('no more answers');
		if (next instanceof Error) throw next;
		return next;
	});
}

function call(fetch: ReturnType<typeof fakeFetch>, index = 0) {
	const [url, init] = fetch.mock.calls[index];
	return {
		url,
		method: init?.method,
		body: init?.body === undefined ? undefined : JSON.parse(init.body as string)
	};
}

describe('admin data layer', () => {
	it('signs in with the password and reports a wrong one', async () => {
		const fetch = fakeFetch(json(200, {}), error(401, 'invalid_password', 'Wrong password'));
		const client = new Api(fetch);

		expect(await admin.login('secret', client)).toEqual({ ok: true, result: undefined });
		expect(call(fetch)).toEqual({
			url: '/api/v1/admin/session',
			method: 'POST',
			body: { password: 'secret' }
		});
		expect(await admin.login('nope', client)).toEqual({
			ok: false,
			code: 'invalid_password',
			message: 'Wrong password'
		});
	});

	it('tells signed in from signed out, and throws for a server problem', async () => {
		const fetch = fakeFetch(
			json(200, {}),
			error(401, 'admin_required', 'Admin sign-in required'),
			error(503, 'unavailable', 'The server is busy. Please try again.')
		);
		const client = new Api(fetch);

		expect(await admin.signedIn(client)).toBe(true);
		expect(call(fetch)).toMatchObject({ url: '/api/v1/admin/session', method: 'GET' });
		expect(await admin.signedIn(client)).toBe(false);
		await expect(admin.signedIn(client)).rejects.toMatchObject({ status: 503 });
	});

	it('signs out', async () => {
		const fetch = fakeFetch(new Response(null, { status: 204 }));
		expect(await admin.logout(new Api(fetch))).toEqual({ ok: true, result: undefined });
		expect(call(fetch)).toMatchObject({ url: '/api/v1/admin/session', method: 'DELETE' });
	});

	it('reads the rooms', async () => {
		const rooms = [
			{ slug: 'attic-1a2b3c', name: 'Attic' },
			{ slug: 'home-ab12cd', name: 'Home' }
		];
		const fetch = fakeFetch(json(200, { rooms }));
		expect(await admin.rooms(new Api(fetch))).toEqual({ ok: true, result: rooms });
		expect(call(fetch)).toMatchObject({ url: '/api/v1/admin/rooms', method: 'GET' });
	});

	it('creates a room and passes the server message on', async () => {
		const room = { slug: 'cabin-1a2b3c', name: 'Cabin' };
		const fetch = fakeFetch(
			json(200, { room }),
			error(422, 'invalid_request', 'Room name cannot be empty')
		);
		const client = new Api(fetch);

		expect(await admin.createRoom('Cabin', 'pw', client)).toEqual({ ok: true, result: room });
		expect(call(fetch)).toEqual({
			url: '/api/v1/admin/rooms',
			method: 'POST',
			body: { name: 'Cabin', password: 'pw' }
		});
		expect(await admin.createRoom(' ', 'pw', client)).toMatchObject({
			ok: false,
			message: 'Room name cannot be empty'
		});
	});

	it('resets a room password', async () => {
		const fetch = fakeFetch(
			json(200, {}),
			error(404, 'room_unavailable', 'Room changed or no longer exists; refresh and try again')
		);
		const client = new Api(fetch);

		expect(await admin.resetPassword('home ab', 'new-pw', client)).toEqual({
			ok: true,
			result: undefined
		});
		expect(call(fetch)).toEqual({
			url: '/api/v1/admin/rooms/home%20ab/password',
			method: 'POST',
			body: { new_password: 'new-pw' }
		});
		expect(await admin.resetPassword('gone', 'new-pw', client)).toMatchObject({
			ok: false,
			code: 'room_unavailable'
		});
	});

	it('recognises an admin session that ended', async () => {
		const fetch = fakeFetch(
			error(401, 'admin_required', 'Admin sign-in required'),
			new TypeError('Failed to fetch')
		);
		const client = new Api(fetch);

		const signedOut = await admin.rooms(client);
		expect(admin.isSignedOut(signedOut)).toBe(true);
		const offline = await admin.rooms(client);
		expect(offline).toMatchObject({ ok: false, code: 'network' });
		expect(admin.isSignedOut(offline)).toBe(false);
	});

	it('lists, issues and revokes invitations', async () => {
		const invitation = {
			id: 3,
			status: 'active',
			created_at: '2026-10-05T09:12:00Z',
			expires_at: '2026-10-12T09:12:00Z',
			revoked_at: null
		};
		const fetch = fakeFetch(
			json(200, { invitations: [invitation] }),
			json(200, { invitation, token: 'secret-token' }),
			json(200, {}),
			error(401, 'admin_required', 'Admin sign-in required')
		);
		const client = new Api(fetch);

		expect(await admin.invitations(client)).toEqual({ ok: true, result: [invitation] });
		expect(call(fetch, 0)).toMatchObject({ url: '/api/v1/admin/invitations', method: 'GET' });
		expect(await admin.issueInvitation(client)).toEqual({
			ok: true,
			result: { invitation, token: 'secret-token' }
		});
		expect(call(fetch, 1)).toEqual({ url: '/api/v1/admin/invitations', method: 'POST', body: {} });
		expect(await admin.revokeInvitation(3, client)).toEqual({ ok: true, result: undefined });
		expect(call(fetch, 2)).toEqual({
			url: '/api/v1/admin/invitations/3/revoke',
			method: 'POST',
			body: {}
		});
		expect(admin.isSignedOut(await admin.revokeInvitation(3, client))).toBe(true);
	});
});
