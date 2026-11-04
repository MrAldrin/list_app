import { describe, expect, it, vi } from 'vitest';
import { Api } from '#lib/data/api.ts';
import { ReminderApi } from './api';

describe('ReminderApi', () => {
	it('uses GET without a write to inspect enrollment and device', async () => {
		const fetch = vi
			.fn()
			.mockImplementation(() =>
				Promise.resolve(new Response(JSON.stringify({ device: null }), { status: 200 }))
			);
		const api = new ReminderApi('my room', new Api(fetch));
		await api.enrollment();
		await api.device();
		expect(fetch.mock.calls.map(([url, init]) => [url, init.method, init.body])).toEqual([
			['/api/v1/rooms/my%20room/reminders/preferences', 'GET', undefined],
			['/api/v1/rooms/my%20room/reminders/preferences/device', 'GET', undefined]
		]);
	});
	it('retries the exact request and operation ID after a lost response', async () => {
		const fetch = vi
			.fn()
			.mockRejectedValueOnce(new TypeError('lost'))
			.mockResolvedValueOnce(new Response('{}', { status: 200 }));
		const api = new ReminderApi('home', new Api(fetch));
		const pending = api.prepare('PATCH', 'preferences', { base_revision: 3, mode: 'quiet' });
		await expect(api.send(pending)).rejects.toThrow();
		await api.send(pending);
		expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
			base_revision: 3,
			mode: 'quiet',
			op_id: pending.body.op_id
		});
	});
});
