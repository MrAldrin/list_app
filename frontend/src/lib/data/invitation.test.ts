import { describe, expect, it } from 'vitest';
import { Api } from './api';
import * as invitation from './invitation';
import { fakeFetch, json } from './test-helpers';

const UNAVAILABLE = 'This invitation is invalid or no longer active.';

function unavailable(): Response {
	return json(404, { error: { code: 'invitation_unavailable', message: UNAVAILABLE } });
}

describe('invitation data layer', () => {
	it('checks a link, with the token in the path', async () => {
		const fetch = fakeFetch(json(200, {}), unavailable());
		const client = new Api(fetch);

		expect(await invitation.active('a/b', client)).toBe(true);
		expect(fetch.mock.calls[0][0]).toBe('/api/v1/invitations/a%2Fb');
		expect(fetch.mock.calls[0][1]?.method).toBe('GET');
		expect(await invitation.active('a/b', client)).toBe(false);
	});

	it('throws for network and server problems, so the page can offer a retry', async () => {
		const fetch = fakeFetch(
			new TypeError('Failed to fetch'),
			json(503, { error: { code: 'unavailable', message: 'busy' } })
		);
		const client = new Api(fetch);

		await expect(invitation.active('t', client)).rejects.toThrow();
		await expect(invitation.active('t', client)).rejects.toMatchObject({ status: 503 });
	});

	it('creates a room and passes the server messages on', async () => {
		const room = { slug: 'abc', name: 'Cabin' };
		const fetch = fakeFetch(
			json(200, { room }),
			json(422, {
				error: { code: 'invalid_request', message: 'Room name must contain 1-100 characters.' }
			}),
			unavailable()
		);
		const client = new Api(fetch);

		expect(await invitation.createRoom('tok', 'Cabin', 'pw', client)).toEqual({
			ok: true,
			result: room
		});
		const [url, init] = fetch.mock.calls[0];
		expect(url).toBe('/api/v1/invitations/tok/rooms');
		expect(init?.method).toBe('POST');
		expect(JSON.parse(init?.body as string)).toEqual({ name: 'Cabin', password: 'pw' });

		const invalid = await invitation.createRoom('tok', ' ', 'pw', client);
		expect(invalid).toMatchObject({
			ok: false,
			message: 'Room name must contain 1-100 characters.'
		});
		expect(invitation.isUnavailableResult(invalid)).toBe(false);

		const gone = await invitation.createRoom('tok', 'Cabin', 'pw', client);
		expect(gone).toMatchObject({ ok: false, message: UNAVAILABLE });
		expect(invitation.isUnavailableResult(gone)).toBe(true);
	});
});
