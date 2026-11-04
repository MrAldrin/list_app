import { describe, expect, it, vi } from 'vitest';
import { Api } from '#lib/data/api.ts';
import { ReminderApi, UnknownWriteOutcome } from './api';

const enrollment = {
	state: 'active',
	revision: 1,
	mode: 'quiet',
	summary_time: '09:00',
	activated_at: '2026-01-01T00:00:00Z'
};
const device = { revision: 1, timezone: 'Europe/Oslo', all_day_time: '09:00', paused: false };
const json = (value: unknown) =>
	new Response(JSON.stringify(value), {
		status: 200,
		headers: { 'Content-Type': 'application/json' }
	});

describe('ReminderApi', () => {
	it('uses GET without a write to inspect enrollment and device', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(json({ enrollment: { state: 'not_enrolled', revision: null } }))
			.mockResolvedValueOnce(json({ device: null }));
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
			.mockResolvedValueOnce(json({ enrollment }));
		const api = new ReminderApi('home', new Api(fetch));
		const pending = api.prepare('PATCH', 'preferences', { base_revision: 3, mode: 'quiet' });
		await expect(api.sendEnrollment(pending)).rejects.toThrow();
		await expect(api.sendEnrollment(pending)).resolves.toEqual(enrollment);
		expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
		expect(JSON.parse(fetch.mock.calls[0][1].body)).toMatchObject({
			base_revision: 3,
			mode: 'quiet',
			op_id: pending.body.op_id
		});
	});
	it.each(['truncated', 'missing fields', 'body read failure'])(
		'treats %s success as unknown for writes',
		async (failure) => {
			const bad =
				failure === 'truncated'
					? new Response('{', { status: 200 })
					: json({ enrollment: { state: 'active' } });
			if (failure === 'body read failure')
				vi.spyOn(bad, 'json').mockRejectedValue(new TypeError('stream failed'));
			const fetch = vi.fn().mockResolvedValueOnce(bad).mockResolvedValueOnce(json({ enrollment }));
			const api = new ReminderApi('home', new Api(fetch));
			const pending = api.prepare('POST', 'enrollment', {
				base_revision: null,
				timezone: 'Europe/Oslo'
			});
			await expect(api.sendEnrollment(pending)).rejects.toBeInstanceOf(UnknownWriteOutcome);
			await expect(api.sendEnrollment(pending)).resolves.toEqual(enrollment);
			expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
		}
	);
	it('rejects missing device fields instead of applying an invalid successful write', async () => {
		const fetch = vi
			.fn()
			.mockResolvedValueOnce(json({ device: { revision: 2 } }))
			.mockResolvedValueOnce(json({ device }));
		const api = new ReminderApi('home', new Api(fetch));
		const pending = api.prepare('PATCH', 'preferences/device', { base_revision: 1, paused: true });
		await expect(api.sendDevice(pending)).rejects.toBeInstanceOf(UnknownWriteOutcome);
		await expect(api.sendDevice(pending)).resolves.toEqual(device);
		expect(fetch.mock.calls[0][1].body).toBe(fetch.mock.calls[1][1].body);
	});
});
