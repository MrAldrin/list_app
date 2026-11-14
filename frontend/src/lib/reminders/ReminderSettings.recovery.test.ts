// @vitest-environment happy-dom
import { flushSync } from 'svelte';
import { expect, it } from 'vitest';
import { json, waitFor } from '#lib/data/test-helpers.ts';
import { button, click, fill } from '#lib/test-support/dom.ts';
import {
	activeEnrollment,
	defaultDevice,
	field,
	reminderFixture,
	settled,
	toggle
} from '#lib/test-support/reminder-fixture.ts';

const saved = 'Saved on this device.';
const unknown = 'The result is unknown.';
const validation = 'Enter summary time as HH:MM (00:00–23:59).';
const notEnrolled = { state: 'not_enrolled', revision: null } as const;

function deviceDraft(target: ParentNode): void {
	fill(field(target, 'Device time zone (IANA)'), 'Europe/Oslo');
	toggle(target, 'Confirm time zone change for all enrolled rooms');
	fill(field(target, 'All-day reminder time'), '13:25');
	toggle(target, 'Pause reminders on this device');
}
function expectDeviceDraft(target: ParentNode, confirmation = true): void {
	expect(field(target, 'Device time zone (IANA)').value).toBe('Europe/Oslo');
	if (confirmation)
		expect(field(target, 'Confirm time zone change for all enrolled rooms').checked).toBe(true);
	else expect(target.textContent).not.toContain('Confirm time zone change for all enrolled rooms');
	expect(field(target, 'All-day reminder time').value).toBe('13:25');
	expect(field(target, 'Pause reminders on this device').checked).toBe(true);
}
async function recoveryFinished(target: ParentNode): Promise<void> {
	await waitFor(() => {
		flushSync();
		expect(target.textContent).not.toContain('Loading settings');
		expect(button(target, 'Close').disabled).toBe(false);
	});
}

it('enrollment 422 keeps validation text and opted-out draft', async () => {
	const fixture = await reminderFixture({
		enrollment: activeEnrollment({ state: 'opted_out', revision: 2 })
	});
	fixture.server.handle = (request) =>
		request.path === 'enrollment' && request.method === 'POST'
			? json(422, { error: { code: 'invalid_request', message: validation } })
			: undefined;
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'Room summary time'), '');
		click(view.target, 'Resume this room');
		await recoveryFinished(view.target);
		expect(view.target.textContent).toContain(validation);
		expect(field(view.target, 'Room summary time').value).toBe('');
		expect(view.target.textContent).toContain('Status: Opted out');
		expect(fixture.writes()).toHaveLength(0);
		// A blank draft is rejected locally. Use a valid draft to reach the
		// separate server-422 classification branch without bypassing validation.
		fill(field(view.target, 'Room summary time'), '12:34');
		click(view.target, 'Resume this room');
		await recoveryFinished(view.target);
		expect(view.target.textContent).toContain(validation);
		expect(view.target.textContent).not.toContain('unavailable or expired');
		expect(view.target.textContent).not.toContain('Retry request');
		expect(view.target.textContent).toContain('Status: Opted out');
		expect(field(view.target, 'Room summary time').value).toBe('12:34');
		expect(fixture.writes().map((request) => request.body)).toEqual([
			{ op_id: expect.any(String), base_revision: 2, mode: 'daily_summary', summary_time: '12:34' }
		]);
		expect(
			fixture.requests.filter((r) => r.method === 'GET' && r.path === 'preferences')
		).toHaveLength(2);
		expect(fixture.server.device).toEqual(defaultDevice());
	} finally {
		await fixture.cleanup();
	}
});

it('failed identity reload retains previous-commit warning across Try loading again', async () => {
	const fixture = await reminderFixture({
		enrollment: activeEnrollment({ state: 'opted_out', revision: 2 })
	});
	let posts = 0;
	let failReads = false;
	fixture.server.handle = (request) => {
		if (request.path === 'enrollment' && request.method === 'POST') {
			if (++posts === 1) {
				fixture.server.enrollment = activeEnrollment({ revision: 3, summary_time: '12:34' });
				return new Response('{', { status: 200 });
			}
			return json(422, { error: { code: 'invalid_request', message: 'A time zone is required.' } });
		}
		if (failReads && request.path === 'preferences' && request.method === 'GET')
			return json(503, { error: { code: 'internal_error', message: 'Identity read unavailable' } });
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'Room summary time'), '12:34');
		click(view.target, 'Resume this room');
		await settled(view.target, unknown);
		fixture.server.enrollment = notEnrolled;
		fixture.server.device = null;
		failReads = true;
		click(view.target, 'Retry request');
		await recoveryFinished(view.target);
		expect(view.target.textContent).toContain(
			'Could not check device identity. Try loading again.'
		);
		expect(view.target.textContent).toContain('previous request may have committed');
		expect(view.target.textContent).not.toContain('Status: Opted out');
		expect(view.target.querySelector('fieldset')).toBeNull();
		expect(fixture.writes()).toHaveLength(2);
		expect(fixture.writes()[1]).toEqual(fixture.writes()[0]);
		click(view.target, 'Try loading again');
		await recoveryFinished(view.target);
		expect(view.target.textContent).toContain('previous request may have committed');
		expect(fixture.writes()).toHaveLength(2);
		failReads = false;
		click(view.target, 'Try loading again');
		await view.loaded();
		expect(view.target.textContent).toContain('Status: Not enrolled');
		expect(view.target.textContent).toContain('unavailable or expired');
		expect(view.target.textContent).toContain('previous request may have committed');
		expect(field(view.target, 'Room summary time').value).toBe('12:34');
		expect(view.target.textContent).not.toContain('Retry the unchanged request');
		expect(button(view.target, 'Enroll this device').disabled).toBe(false);
		expect(fixture.writes()).toHaveLength(2);
		expect(fixture.writes()[0].body).not.toHaveProperty('timezone');
	} finally {
		await fixture.cleanup();
	}
});

it.each([
	{ otherRoom: false, commitUnknown: false },
	{ otherRoom: false, commitUnknown: true },
	{ otherRoom: true, commitUnknown: false },
	{ otherRoom: true, commitUnknown: true }
])(
	'expired enroll or resume requires explicit new identity $otherRoom/$commitUnknown',
	async ({ otherRoom, commitUnknown }) => {
		const fixture = await reminderFixture({
			slug: otherRoom ? 'cabin' : 'home',
			enrollment: otherRoom ? notEnrolled : activeEnrollment({ state: 'opted_out', revision: 2 }),
			device: defaultDevice({ timezone: 'UTC' })
		});
		let expired = !commitUnknown;
		let newIdentity = false;
		fixture.server.handle = (request) => {
			if (request.path !== 'enrollment' || request.method !== 'POST') return;
			if (expired && !newIdentity)
				return json(422, {
					error: { code: 'invalid_request', message: 'A time zone is required.' }
				});
			fixture.server.enrollment = activeEnrollment({
				revision: newIdentity ? 1 : 3,
				summary_time: '12:34'
			});
			if (!newIdentity) return new Response('{', { status: 200 });
			fixture.server.device = defaultDevice();
			return json(200, { enrollment: fixture.server.enrollment });
		};
		const view = fixture.view('settings');
		try {
			await view.loaded();
			fill(field(view.target, 'Room summary time'), '12:34');
			deviceDraft(view.target);
			const action = otherRoom ? 'Enroll this device' : 'Resume this room';
			if (commitUnknown) {
				click(view.target, action);
				await settled(view.target, unknown);
				expect(view.target.querySelector('fieldset')!.disabled).toBe(true);
				expired = true;
			}
			fixture.server.enrollment = notEnrolled;
			fixture.server.device = null;
			click(view.target, commitUnknown ? 'Retry request' : action);
			await view.loaded();
			await recoveryFinished(view.target);
			expect(view.target.textContent).toContain('Status: Not enrolled');
			expect(view.target.textContent).toContain('unavailable or expired');
			if (commitUnknown)
				expect(view.target.textContent).toContain('previous request may have committed');
			else expect(view.target.textContent).not.toContain('previous request may have committed');
			expect(field(view.target, 'Room summary time').value).toBe('12:34');
			expect(field<HTMLSelectElement>(view.target, 'Room reminder mode').value).toBe(
				'daily_summary'
			);
			expect(field(view.target, 'Time zone for this device (IANA)').value).toBe('Europe/Oslo');
			expect(view.target.textContent).not.toContain('Retry the unchanged request');
			const old = fixture.writes();
			expect(old).toHaveLength(commitUnknown ? 2 : 1);
			if (commitUnknown) expect(old[1]).toEqual(old[0]);
			for (const request of old)
				expect(request.body).toEqual({
					op_id: expect.any(String),
					base_revision: otherRoom ? null : 2,
					mode: 'daily_summary',
					summary_time: '12:34'
				});
			newIdentity = true;
			click(view.target, 'Enroll this device');
			await settled(view.target, saved);
			expect(view.target.textContent).toContain('Status: Active');
			const fresh = fixture.writes().at(-1)!;
			expect(fresh.body).toEqual({
				op_id: expect.any(String),
				base_revision: null,
				timezone: 'Europe/Oslo',
				mode: 'daily_summary',
				summary_time: '12:34'
			});
			expect(fresh.body.op_id).not.toBe(old[0].body.op_id);
			// The new installation now uses the draft zone, so confirmation hides.
			expectDeviceDraft(view.target, false);
			expect(fixture.writes()).toHaveLength(old.length + 1);
			expect(fixture.api.sendOp).not.toHaveBeenCalled();
		} finally {
			await fixture.cleanup();
		}
	}
);

it.each([false, true])(
	'missing identity clears pending retry but retains draft until explicit enrollment: retry=%s',
	async (retry) => {
		const fixture = await reminderFixture({ device: defaultDevice({ timezone: 'UTC' }) });
		let missing = false;
		fixture.server.handle = (request) => {
			if (request.path === 'preferences' && request.method === 'PATCH') {
				if (missing)
					return json(403, { error: { code: 'not_enrolled', message: 'No device identity' } });
				fixture.server.enrollment = activeEnrollment({ revision: 2, summary_time: '11:45' });
				return new Response('{', { status: 200 });
			}
			if (request.path === 'enrollment' && request.method === 'POST') {
				fixture.server.enrollment = activeEnrollment({ summary_time: '11:45' });
				fixture.server.device = defaultDevice({ timezone: 'UTC' });
				return json(200, { enrollment: fixture.server.enrollment });
			}
		};
		const view = fixture.view('settings');
		try {
			await view.loaded();
			fill(field(view.target, 'Room summary time'), '11:45');
			if (retry) {
				click(view.target, 'Save room settings');
				await settled(view.target, unknown);
			}
			missing = true;
			fixture.server.enrollment = notEnrolled;
			fixture.server.device = null;
			click(view.target, retry ? 'Retry request' : 'Save room settings');
			await view.loaded();
			await recoveryFinished(view.target);
			expect(view.target.textContent).toContain('Status: Not enrolled');
			expect(view.target.textContent).toContain('previous request may have committed');
			expect(view.target.textContent).toContain('cannot be retried on a new installation');
			expect(view.target.textContent).not.toContain('Retry the unchanged request');
			expect(
				[...view.target.querySelectorAll('button')].some(
					(node) => node.textContent === 'Retry request'
				)
			).toBe(false);
			expect(field(view.target, 'Room summary time').value).toBe('11:45');
			expect(field(view.target, 'Time zone for this device (IANA)').value).toBe('UTC');
			const old = fixture.writes();
			expect(old).toHaveLength(retry ? 2 : 1);
			if (retry) expect(old[1]).toEqual(old[0]);
			click(view.target, 'Enroll this device');
			await settled(view.target, saved);
			expect(view.target.textContent).toContain('Status: Active');
			expect(field(view.target, 'Room summary time').value).toBe('11:45');
			const fresh = fixture.writes().at(-1)!;
			expect(fresh.body).toEqual({
				op_id: expect.any(String),
				base_revision: null,
				timezone: 'UTC',
				mode: 'daily_summary',
				summary_time: '11:45'
			});
			expect(fresh.body.op_id).not.toBe(old[0].body.op_id);
			expect(fixture.writes()).toHaveLength(old.length + 1);
		} finally {
			await fixture.cleanup();
		}
	}
);

it('retry button resends pending request unchanged after a lost committed PATCH', async () => {
	const fixture = await reminderFixture();
	let attempts = 0;
	fixture.server.handle = (request) => {
		if (request.path !== 'preferences' || request.method !== 'PATCH') return;
		fixture.server.enrollment = activeEnrollment({ revision: 2, summary_time: '11:45' });
		if (++attempts === 1) throw new TypeError('connection lost after commit');
		return json(200, { enrollment: fixture.server.enrollment });
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'Room summary time'), '11:45');
		click(view.target, 'Save room settings');
		await settled(view.target, unknown);
		expect(fixture.server.enrollment).toMatchObject({ revision: 2, summary_time: '11:45' });
		expect(view.target.querySelector('fieldset')!.disabled).toBe(true);
		expect(button(view.target, 'Close').disabled).toBe(true);
		click(view.target, 'Retry request');
		await settled(view.target, saved);
		expect(fixture.writes()).toHaveLength(2);
		expect(fixture.writes()[1]).toEqual(fixture.writes()[0]);
		expect(fixture.writes()[0].body).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			mode: 'daily_summary',
			summary_time: '11:45'
		});
		expect(view.target.querySelector('fieldset')!.disabled).toBe(false);
		expect(view.target.textContent).not.toContain('Retry the unchanged request');
	} finally {
		await fixture.cleanup();
	}
});

it('device save keeps opted-out status until Resume', async () => {
	const fixture = await reminderFixture({
		enrollment: activeEnrollment({ state: 'opted_out', revision: 2 })
	});
	fixture.server.handle = (request) => {
		if (request.path === 'preferences/device' && request.method === 'PATCH') {
			fixture.server.device = defaultDevice({ revision: 2, all_day_time: '13:25' });
			return json(200, { device: fixture.server.device });
		}
		if (request.path === 'enrollment' && request.method === 'POST') {
			fixture.server.enrollment = activeEnrollment({ revision: 3 });
			return json(200, { enrollment: fixture.server.enrollment });
		}
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'All-day reminder time'), '13:25');
		click(view.target, 'Save device settings');
		await settled(view.target, saved);
		expect(view.target.textContent).toContain('Status: Opted out');
		expect(view.target.textContent).not.toContain('Status: Active');
		expect(button(view.target, 'Resume this room').disabled).toBe(false);
		expect(fixture.writes().map((r) => r.path)).toEqual(['preferences/device']);
		click(view.target, 'Resume this room');
		await settled(view.target, 'Status: Active');
		await recoveryFinished(view.target);
		expect(fixture.writes().map((r) => ({ method: r.method, path: r.path }))).toEqual([
			{ method: 'PATCH', path: 'preferences/device' },
			{ method: 'POST', path: 'enrollment' }
		]);
		expect(fixture.writes()[1].body).toEqual({
			op_id: expect.any(String),
			base_revision: 2,
			mode: 'daily_summary',
			summary_time: '09:00'
		});
	} finally {
		await fixture.cleanup();
	}
});

it('optout and resume preserve unrelated room and device drafts', async () => {
	const fixture = await reminderFixture({ device: defaultDevice({ timezone: 'UTC' }) });
	fixture.server.handle = (request) => {
		if (request.path === 'preferences' && request.method === 'PATCH') {
			fixture.server.enrollment = activeEnrollment({ state: 'opted_out', revision: 2 });
			return json(200, { enrollment: fixture.server.enrollment });
		}
		if (request.path === 'enrollment' && request.method === 'POST') {
			fixture.server.enrollment = activeEnrollment({ revision: 3, summary_time: '11:45' });
			return json(200, { enrollment: fixture.server.enrollment });
		}
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'Room summary time'), '11:45');
		click(view.target, 'Opt out of this room');
		await settled(view.target, 'Status: Opted out');
		expect(field(view.target, 'Room summary time').value).toBe('11:45');
		expect(field<HTMLSelectElement>(view.target, 'Room reminder mode').value).toBe('daily_summary');
		deviceDraft(view.target);
		click(view.target, 'Resume this room');
		await settled(view.target, 'Status: Active');
		await recoveryFinished(view.target);
		expectDeviceDraft(view.target);
		expect(field(view.target, 'Room summary time').value).toBe('11:45');
		expect(field<HTMLSelectElement>(view.target, 'Room reminder mode').value).toBe('daily_summary');
		expect(fixture.writes().map((request) => request.body)).toEqual([
			{ op_id: expect.any(String), base_revision: 1, opted_out: true },
			{ op_id: expect.any(String), base_revision: 2, mode: 'daily_summary', summary_time: '11:45' }
		]);
		expect(fixture.writes().map((request) => request.path)).toEqual(['preferences', 'enrollment']);
		expect(fixture.server.device).toEqual(defaultDevice({ timezone: 'UTC' }));
	} finally {
		await fixture.cleanup();
	}
});

it.each([
	{ action: 'room', malformed: '{' },
	{ action: 'room', malformed: '{}' },
	{ action: 'enroll', malformed: '{' },
	{ action: 'optout', malformed: '{}' },
	{ action: 'device', malformed: '{}' }
])(
	'unusable successes keep pending request and disable edits for $action/$malformed',
	async ({ action, malformed }) => {
		const fixture = await reminderFixture(
			action === 'enroll' ? { enrollment: notEnrolled, device: null } : {}
		);
		const path =
			action === 'enroll'
				? 'enrollment'
				: action === 'device'
					? 'preferences/device'
					: 'preferences';
		let attempts = 0;
		fixture.server.handle = (request) => {
			if (request.path !== path || request.method === 'GET') return;
			fixture.server.enrollment = activeEnrollment({
				state: action === 'optout' ? 'opted_out' : 'active',
				revision: action === 'enroll' ? 1 : 2,
				summary_time: action === 'room' ? '11:45' : '09:00'
			});
			fixture.server.device = defaultDevice({
				revision: action === 'device' ? 2 : 1,
				all_day_time: action === 'device' ? '13:25' : '09:00'
			});
			return ++attempts === 1
				? new Response(malformed, { status: 200 })
				: json(
						200,
						action === 'device'
							? { device: fixture.server.device }
							: { enrollment: fixture.server.enrollment }
					);
		};
		const view = fixture.view('settings');
		try {
			await view.loaded();
			if (action === 'room') fill(field(view.target, 'Room summary time'), '11:45');
			if (action === 'device') fill(field(view.target, 'All-day reminder time'), '13:25');
			click(
				view.target,
				{
					room: 'Save room settings',
					enroll: 'Enroll this device',
					optout: 'Opt out of this room',
					device: 'Save device settings'
				}[action]!
			);
			await settled(view.target, unknown);
			expect(fixture.writes()).toHaveLength(1);
			expect(view.target.querySelector('fieldset')!.disabled).toBe(true);
			expect(field(view.target, 'Room reminder mode').closest('fieldset')!.disabled).toBe(true);
			expect(button(view.target, 'Close').disabled).toBe(true);
			expect(view.onClose).not.toHaveBeenCalled();
			const original = fixture.writes()[0];
			expect(original).toMatchObject({ method: action === 'enroll' ? 'POST' : 'PATCH', path });
			if (action === 'optout')
				expect(original.body).toEqual({
					op_id: expect.any(String),
					base_revision: 1,
					opted_out: true
				});
			else if (action !== 'device')
				expect(original.body).toEqual({
					op_id: expect.any(String),
					base_revision: action === 'enroll' ? null : 1,
					...(action === 'enroll' ? { timezone: 'Europe/Oslo' } : {}),
					mode: 'daily_summary',
					summary_time: action === 'room' ? '11:45' : '09:00'
				});
			else
				expect(original.body).toMatchObject({
					op_id: expect.any(String),
					base_revision: 1,
					all_day_time: '13:25'
				});
			click(view.target, 'Retry request');
			await settled(view.target, saved);
			expect(fixture.writes()).toHaveLength(2);
			expect(fixture.writes()[1]).toEqual(original);
			expect(view.target.querySelector('fieldset')!.disabled).toBe(false);
			expect(button(view.target, 'Close').disabled).toBe(false);
			expect(view.target.textContent).not.toContain('Retry the unchanged request');
			expect(view.target.textContent).toContain(
				action === 'optout' ? 'Status: Opted out' : 'Status: Active'
			);
			expect(fixture.api.sendOp).not.toHaveBeenCalled();
		} finally {
			await fixture.cleanup();
		}
	}
);
