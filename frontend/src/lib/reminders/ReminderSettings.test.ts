// @vitest-environment happy-dom
import { flushSync } from 'svelte';
import { expect, it } from 'vitest';
import { json, waitFor } from '#lib/data/test-helpers.ts';
import { button, click, fill } from '#lib/test-support/dom.ts';
import {
	activeEnrollment,
	defaultDevice,
	field,
	network,
	reminderFixture,
	reminderPolicy,
	settled,
	toggle
} from '#lib/test-support/reminder-fixture.ts';

function dialog(target: ParentNode, title: string): HTMLDialogElement {
	const found = [...target.querySelectorAll('dialog')].find(
		(node) => node.querySelector('h2')?.textContent === title
	);
	expect(found, `dialog ${title}`).toBeDefined();
	return found!;
}
const saved = 'Saved on this device.';

// The production menu is gated until S3. Mount the real editor/settings
// composition directly; menu opening and native Schedule selection stay in
// the paused browser journey. Do not replace the feature flag or select code.
it('policy scheduled save reopens enrollment settings as scheduled', async () => {
	const fixture = await reminderFixture({
		enrollment: { state: 'not_enrolled', revision: null },
		device: null
	});
	const scheduled = reminderPolicy('room', { preset: 'scheduled', revision: 2 });
	const original = reminderPolicy('room', { preset: 'daily_summary', summary_enabled: true });
	fixture.server.policy = { policy: original, effective: original };
	fixture.server.handle = (request) => {
		if (
			request.method === 'GET' &&
			request.path === 'policy' &&
			fixture.server.enrollment.state === 'not_enrolled'
		)
			return json(403, { error: { code: 'not_enrolled', message: 'Enrollment required' } });
		if (request.path === 'enrollment' && request.method === 'POST') {
			fixture.server.enrollment = activeEnrollment();
			fixture.server.device = defaultDevice();
			return json(200, { enrollment: fixture.server.enrollment });
		}
		if (request.path === 'policy' && request.method === 'PUT') {
			fixture.server.enrollment = activeEnrollment({ mode: 'scheduled', revision: 3 });
			fixture.server.policy = {
				policy: { ...scheduled, revision: 3 },
				effective: { ...scheduled, revision: 3 }
			};
			return json(200, fixture.server.policy);
		}
	};
	const enrollmentEditor = fixture.view('room');
	try {
		await settled(enrollmentEditor.target, 'Explicitly enroll or resume');
		click(enrollmentEditor.target, 'Open enrollment settings');
		const settings = dialog(enrollmentEditor.target, 'Personal reminders');
		await settled(settings, 'Status: Not enrolled');
		click(settings, 'Enroll this device');
		await settled(settings, saved);
		expect(settings.textContent).toContain('Status: Active');
		click(settings, 'Close');
		await enrollmentEditor.loaded();
		expect(enrollmentEditor.target.querySelectorAll('dialog')).toHaveLength(1);
		expect(field<HTMLSelectElement>(enrollmentEditor.target, 'Schedule').value).toBe(
			'daily_summary'
		);
		await enrollmentEditor.destroy();
		// Native Daily summary → Scheduled selection is not available here.
		// Start the next mounted editor from a consistent scheduled API snapshot.
		fixture.server.policy = { policy: scheduled, effective: scheduled };
		fixture.server.enrollment = activeEnrollment({ mode: 'scheduled', revision: 2 });
		const editor = fixture.view('room');
		await editor.loaded();
		expect(field<HTMLSelectElement>(editor.target, 'Schedule').value).toBe('scheduled');
		click(editor.target, 'Save policy');
		await settled(editor.target, saved);
		expect(fixture.writes().map((request) => ({ path: request.path, body: request.body }))).toEqual(
			[
				{
					path: 'enrollment',
					body: {
						op_id: expect.any(String),
						base_revision: null,
						timezone: 'Europe/Oslo',
						mode: 'daily_summary',
						summary_time: '09:00'
					}
				},
				{
					path: 'policy',
					body: {
						op_id: expect.any(String),
						base_revision: 2,
						state: 'replace',
						preset: 'scheduled'
					}
				}
			]
		);
		click(editor.target, 'Close');
		expect(editor.onClose).toHaveBeenCalledOnce();
		await editor.destroy();
		const reopened = fixture.view('settings');
		await reopened.loaded();
		expect(field<HTMLSelectElement>(reopened.target, 'Room reminder mode').value).toBe('scheduled');
		expect(reopened.target.textContent).toContain('Status: Active');
		expect(reopened.target.textContent).not.toContain('Room summary time');
	} finally {
		await fixture.cleanup();
	}
});

it('body read failure keeps pending PATCH through Retry', async () => {
	const fixture = await reminderFixture({ enrollment: activeEnrollment({ mode: 'quiet' }) });
	let attempts = 0;
	fixture.server.handle = (request) => {
		if (request.path !== 'preferences' || request.method !== 'PATCH') return;
		fixture.server.enrollment = activeEnrollment({ mode: 'quiet', revision: 2 });
		const response = json(200, { enrollment: fixture.server.enrollment });
		if (++attempts === 1)
			Object.defineProperty(response, 'json', {
				value: async () => {
					throw new TypeError('body stream failed after commit');
				}
			});
		return response;
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		click(view.target, 'Save room settings');
		await settled(
			view.target,
			'The result is unknown. Retry the same request when connected; your edits are kept.'
		);
		expect(attempts).toBe(1);
		expect(view.target.querySelector('fieldset')!.disabled).toBe(true);
		expect(button(view.target, 'Close').disabled).toBe(true);
		click(view.target, 'Retry request');
		await settled(view.target, saved);
		expect(fixture.writes()).toHaveLength(2);
		expect(fixture.writes()[1]).toEqual(fixture.writes()[0]);
		expect(fixture.writes()[0]).toMatchObject({
			method: 'PATCH',
			path: 'preferences',
			body: { op_id: expect.any(String), base_revision: 1, mode: 'quiet', summary_time: '09:00' }
		});
		expect(view.target.querySelector('fieldset')!.disabled).toBe(false);
		expect(view.target.textContent).not.toContain('Retry the unchanged request');
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await fixture.cleanup();
	}
});

it('revision conflict disables Save until explicit reload and preserves draft', async () => {
	const fixture = await reminderFixture();
	let attempts = 0;
	fixture.server.handle = (request) => {
		if (request.path !== 'preferences' || request.method !== 'PATCH') return;
		if (++attempts === 1) {
			fixture.server.enrollment = activeEnrollment({ revision: 2, mode: 'quiet' });
			return json(409, { error: { code: 'revision_conflict', message: 'Changed elsewhere' } });
		}
		fixture.server.enrollment = activeEnrollment({ revision: 3, summary_time: '11:45' });
		return json(200, { enrollment: fixture.server.enrollment });
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'Room summary time'), '11:45');
		click(view.target, 'Save room settings');
		await settled(
			view.target,
			'Settings changed elsewhere. Load latest revisions and review your edits.'
		);
		expect(view.target.querySelector('fieldset')!.disabled).toBe(true);
		expect(field(view.target, 'Room summary time').value).toBe('11:45');
		expect(
			fixture.requests.filter(
				(request) => request.method === 'GET' && request.path === 'preferences'
			)
		).toHaveLength(1);
		click(view.target, 'Load latest revisions');
		await waitFor(() => {
			flushSync();
			expect(view.target.querySelector('fieldset')!.disabled).toBe(false);
		});
		expect(view.target.textContent).toContain(
			'Latest revisions loaded. Your edits remain; review them before saving.'
		);
		expect(
			fixture.requests.filter(
				(request) => request.method === 'GET' && request.path === 'preferences'
			)
		).toHaveLength(2);
		expect(field(view.target, 'Room summary time').value).toBe('11:45');
		expect(field<HTMLSelectElement>(view.target, 'Room reminder mode').value).toBe('daily_summary');
		expect(view.target.querySelector('fieldset')!.disabled).toBe(false);
		expect(button(view.target, 'Save room settings').disabled).toBe(false);
		click(view.target, 'Save room settings');
		await settled(view.target, saved);
		expect(fixture.writes().map((request) => request.body)).toEqual([
			{ op_id: expect.any(String), base_revision: 1, mode: 'daily_summary', summary_time: '11:45' },
			{ op_id: expect.any(String), base_revision: 2, mode: 'daily_summary', summary_time: '11:45' }
		]);
		expect(fixture.writes()[0].body.op_id).not.toBe(fixture.writes()[1].body.op_id);
	} finally {
		await fixture.cleanup();
	}
});

it('invalid time blocks enroll and custom summary toggles retain time', async () => {
	const fixture = await reminderFixture({
		enrollment: { state: 'not_enrolled', revision: null },
		device: null
	});
	fixture.server.handle = (request) => {
		if (request.path === 'enrollment' && request.method === 'POST') {
			fixture.server.enrollment = activeEnrollment({ summary_time: '13:45' });
			fixture.server.device = defaultDevice();
			return json(200, { enrollment: fixture.server.enrollment });
		}
		if (request.path === 'policy' && request.method === 'PUT') {
			const policy = reminderPolicy('room', {
				summary_enabled: Boolean(request.body.summary_enabled),
				revision: fixture.server.policy.policy.revision + 1
			});
			fixture.server.policy = { policy, effective: policy };
			return json(200, fixture.server.policy);
		}
	};
	const first = fixture.view('settings');
	try {
		await first.loaded();
		expect(field(first.target, 'Room summary time').type).toBe('text');
		expect(field(first.target, 'Room summary time').inputMode).toBe('text');
		fill(field(first.target, 'Room summary time'), '24:00');
		click(first.target, 'Enroll this device');
		await waitFor(() => {
			flushSync();
			expect(first.target.querySelector('fieldset')!.disabled).toBe(false);
		});
		expect(first.target.textContent).toContain('Enter summary time as HH:MM (00:00–23:59).');
		expect(first.target.textContent).toContain('Status: Not enrolled');
		expect(fixture.writes()).toHaveLength(0);
		fill(field(first.target, 'Room summary time'), '13:45');
		click(first.target, 'Enroll this device');
		await settled(first.target, saved);
		expect(fixture.writes()[0].body).toMatchObject({ summary_time: '13:45' });
		await first.destroy();
		// Seed each native-select branch; mode toggles themselves stay in a browser.
		for (const mode of ['quiet', 'scheduled', 'custom'] as const) {
			fixture.server.enrollment = activeEnrollment({ mode, summary_time: '13:45' });
			const view = fixture.view('settings');
			await view.loaded();
			expect(view.target.textContent).not.toContain('Room summary time');
			if (mode === 'custom') {
				for (const enabled of [true, false, true]) {
					click(view.target, 'Edit custom room rules');
					const editor = dialog(view.target, 'Personal room reminders');
					await settled(editor, 'Choose your own reminder rules');
					toggle(editor, 'Include daily summary');
					click(editor, 'Save policy');
					await settled(editor, saved);
					click(editor, 'Close');
					await settled(view.target, 'Status: Active');
					await settled(view.target, 'Save or enroll with Custom first, then edit its rules.');
					// Wait for the actual GET/refresh, not only the unchanged status.
					await view.loaded();
					if (enabled) expect(field(view.target, 'Room summary time').value).toBe('13:45');
					else expect(view.target.textContent).not.toContain('Room summary time');
				}
			}
			await view.destroy();
		}
		expect(
			fixture
				.writes()
				.filter((request) => request.path === 'policy')
				.map((request) => request.body.summary_enabled)
		).toEqual([true, false, true]);
	} finally {
		await fixture.cleanup();
	}
});

it('custom summary read failure exposes fallback and Retry', async () => {
	const fixture = await reminderFixture({ enrollment: activeEnrollment({ mode: 'custom' }) });
	let reads = 0;
	fixture.server.handle = (request) =>
		request.path === 'policy' && request.method === 'GET' && ++reads === 1
			? json(503, { error: { code: 'internal_error', message: 'Policy unavailable' } })
			: undefined;
	const view = fixture.view('settings');
	try {
		await view.loaded();
		expect(view.target.textContent).toContain(
			'Could not check whether the custom policy includes a summary.'
		);
		expect(field(view.target, 'Room summary time').value).toBe('09:00');
		fill(field(view.target, 'All-day reminder time'), '14:25');
		click(view.target, 'Retry custom summary check');
		await settled(view.target, 'Choose your own reminder rules and optional summary.');
		// Retry has no loading spinner; use the disappeared alert as completion.
		await waitFor(() => {
			flushSync();
			expect(view.target.querySelector('[role="alert"]')).toBeNull();
		});
		expect(reads).toBe(2);
		expect(view.target.textContent).not.toContain('Room summary time');
		expect(view.target.textContent).not.toContain('Retry custom summary check');
		expect(field(view.target, 'All-day reminder time').value).toBe('14:25');
		expect(fixture.writes()).toHaveLength(0);
	} finally {
		await fixture.cleanup();
	}
});

it('mode save refreshes custom summary metadata after a concurrent policy change', async () => {
	const fixture = await reminderFixture({
		enrollment: activeEnrollment({ mode: 'custom', summary_time: '13:45' })
	});
	fixture.server.handle = (request) => {
		if (request.path === 'policy' && request.method === 'PUT') {
			const policy = reminderPolicy('room', { summary_enabled: true, revision: 2 });
			fixture.server.policy = { policy, effective: policy };
			return json(200, fixture.server.policy);
		}
		if (request.path === 'preferences' && request.method === 'PATCH') {
			// Another policy write can finish while this preferences write is in flight.
			const policy = reminderPolicy('room', { summary_enabled: false, revision: 3 });
			fixture.server.policy = { policy, effective: policy };
			fixture.server.enrollment = activeEnrollment({
				mode: 'custom',
				summary_time: '13:45',
				revision: 2
			});
			return json(200, { enrollment: fixture.server.enrollment });
		}
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		expect(view.target.textContent).not.toContain('Room summary time');
		click(view.target, 'Edit custom room rules');
		const editor = dialog(view.target, 'Personal room reminders');
		await settled(editor, 'Choose your own reminder rules');
		toggle(editor, 'Include daily summary');
		click(editor, 'Save policy');
		await settled(editor, saved);
		click(editor, 'Close');
		await view.loaded();
		expect(field(view.target, 'Room summary time').value).toBe('13:45');
		const before = fixture.requests.filter(
			(request) => request.path === 'policy' && request.method === 'GET'
		).length;
		click(view.target, 'Save room settings');
		await settled(view.target, saved);
		expect(
			fixture.requests.filter((request) => request.path === 'policy' && request.method === 'GET')
		).toHaveLength(before + 1);
		expect(fixture.writes().at(-1)?.body).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			mode: 'custom',
			summary_time: '13:45'
		});
		expect(fixture.server.policy.policy).toMatchObject({
			preset: 'custom',
			summary_enabled: false
		});
		expect(view.target.textContent).not.toContain('Room summary time');
	} finally {
		await fixture.cleanup();
	}
});

it('device controls serialize exact draft and reopen persisted values', async () => {
	const fixture = await reminderFixture();
	const changed = defaultDevice({
		revision: 2,
		quiet_hours: { start: '21:15', end: '07:30' },
		daily_cap: 23,
		spacing_minutes: 17,
		overdue_repeat_days: 9
	});
	let attempts = 0;
	fixture.server.handle = (request) => {
		if (request.path !== 'preferences/device' || request.method !== 'PATCH') return;
		fixture.server.device =
			++attempts <= 2
				? changed
				: attempts === 3
					? { ...changed, revision: 3, quiet_hours: null, overdue_repeat_days: null }
					: defaultDevice({ revision: 5, content_privacy: 'names' });
		return json(200, attempts === 1 ? {} : { device: fixture.server.device });
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		expect(field(view.target, 'Enable quiet hours').checked).toBe(true);
		expect(field(view.target, 'Quiet hours start').value).toBe('22:00');
		expect(field(view.target, 'Quiet hours end').value).toBe('08:00');
		expect(field(view.target, 'Daily cap (1–50)').value).toBe('10');
		expect(field(view.target, 'Minimum spacing in minutes (1–60)').value).toBe('10');
		expect(field<HTMLSelectElement>(view.target, 'Notification content privacy').value).toBe(
			'generic'
		);
		expect(field(view.target, 'Enable overdue repeat').checked).toBe(false);
		fill(field(view.target, 'Quiet hours start'), '21:15');
		fill(field(view.target, 'Quiet hours end'), '07:30');
		fill(field(view.target, 'Daily cap (1–50)'), '23');
		fill(field(view.target, 'Minimum spacing in minutes (1–60)'), '17');
		toggle(view.target, 'Enable overdue repeat');
		fill(field(view.target, 'Overdue repeat interval in days (1–30)'), '9');
		click(view.target, 'Save device settings');
		await settled(view.target, 'The result is unknown.');
		for (const label of ['Quiet hours start', 'Notification content privacy'])
			expect(field(view.target, label).closest('fieldset')!.disabled).toBe(true);
		click(view.target, 'Retry request');
		await settled(view.target, saved);
		expect(fixture.writes()).toHaveLength(2);
		expect(fixture.writes()[1]).toEqual(fixture.writes()[0]);
		expect(fixture.writes()[0].body).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			timezone: 'Europe/Oslo',
			all_day_time: '09:00',
			paused: false,
			quiet_hours: { start: '21:15', end: '07:30' },
			daily_cap: 23,
			spacing_minutes: 17,
			content_privacy: 'generic',
			overdue_repeat_days: 9
		});
		await view.destroy();
		const reopened = fixture.view('settings');
		await reopened.loaded();
		for (const [label, value] of [
			['Quiet hours start', '21:15'],
			['Quiet hours end', '07:30'],
			['Daily cap (1–50)', '23'],
			['Minimum spacing in minutes (1–60)', '17'],
			['Overdue repeat interval in days (1–30)', '9']
		])
			expect(field(reopened.target, label).value).toBe(value);
		expect(field(reopened.target, 'Enable overdue repeat').checked).toBe(true);
		toggle(reopened.target, 'Enable quiet hours');
		toggle(reopened.target, 'Enable overdue repeat');
		click(reopened.target, 'Save device settings');
		await settled(reopened.target, saved);
		expect(fixture.writes()[2].body).toMatchObject({
			base_revision: 2,
			quiet_hours: null,
			overdue_repeat_days: null
		});
		await reopened.destroy();
		const cleared = fixture.view('settings');
		await cleared.loaded();
		expect(field(cleared.target, 'Enable quiet hours').checked).toBe(false);
		expect(field(cleared.target, 'Enable overdue repeat').checked).toBe(false);
		expect(cleared.target.textContent).not.toContain('Quiet hours start');
		expect(cleared.target.textContent).not.toContain('Overdue repeat interval in days');
		await cleared.destroy();
		// Native Generic → Names selection stays in the browser. A real-shaped
		// saved Names response must still initialize and serialize the value.
		fixture.server.device = defaultDevice({ revision: 4, content_privacy: 'names' });
		const names = fixture.view('settings');
		await names.loaded();
		expect(field<HTMLSelectElement>(names.target, 'Notification content privacy').value).toBe(
			'names'
		);
		click(names.target, 'Save device settings');
		await settled(names.target, saved);
		expect(fixture.writes()[3].body).toMatchObject({ base_revision: 4, content_privacy: 'names' });
	} finally {
		await fixture.cleanup();
	}
});

it('invalid device controls send no PATCH and keep offline draft', async () => {
	const fixture = await reminderFixture();
	const view = fixture.view('settings');
	try {
		await view.loaded();
		toggle(view.target, 'Enable overdue repeat');
		for (const [label, maximum, valid] of [
			['Daily cap (1–50)', 51, '10'],
			['Minimum spacing in minutes (1–60)', 61, '10'],
			['Overdue repeat interval in days (1–30)', 31, '1']
		] as const) {
			for (const invalid of ['0', String(maximum), '1.5', '']) {
				fill(field(view.target, label), invalid);
				click(view.target, 'Save device settings');
				expect(view.target.textContent).toContain('use whole numbers.');
				expect(fixture.writes(), `${label}=${invalid}`).toHaveLength(0);
			}
			fill(field(view.target, label), valid);
		}
		fill(field(view.target, 'Quiet hours end'), '22:00');
		click(view.target, 'Save device settings');
		expect(view.target.textContent).toContain('quiet hours need different start and end times.');
		expect(fixture.writes()).toHaveLength(0);
		fill(field(view.target, 'Quiet hours end'), '08:00');
		fill(field(view.target, 'Daily cap (1–50)'), '42');
		network(false);
		expect(button(view.target, 'Save device settings').disabled).toBe(true);
		expect(field(view.target, 'Daily cap (1–50)').value).toBe('42');
		network(true);
		expect(button(view.target, 'Save device settings').disabled).toBe(false);
		expect(field(view.target, 'Daily cap (1–50)').value).toBe('42');
		expect(fixture.writes()).toHaveLength(0);
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await fixture.cleanup();
	}
});

it.each(['13:25', '09:00'])(
	'device response initializes all-day field per handle to %s',
	async (allDay) => {
		const fixture = await reminderFixture({
			device: defaultDevice({
				all_day_time: allDay,
				content_privacy: allDay === '13:25' ? 'names' : 'generic'
			})
		});
		const view = fixture.view('settings');
		try {
			await view.loaded();
			expect(field(view.target, 'All-day reminder time').value).toBe(allDay);
			expect(field<HTMLSelectElement>(view.target, 'Notification content privacy').value).toBe(
				allDay === '13:25' ? 'names' : 'generic'
			);
			expect(fixture.writes()).toHaveLength(0);
		} finally {
			await fixture.cleanup();
		}
	}
);

it('second room enrollment preserves existing device draft', async () => {
	const fixture = await reminderFixture({
		slug: 'cabin-ab12cd',
		enrollment: { state: 'not_enrolled', revision: null }
	});
	fixture.server.handle = (request) => {
		if (request.path !== 'enrollment' || request.method !== 'POST') return;
		fixture.server.enrollment = activeEnrollment();
		return json(200, { enrollment: fixture.server.enrollment });
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'Device time zone (IANA)'), 'Pacific/Kiritimati');
		toggle(view.target, 'Confirm time zone change for all enrolled rooms');
		fill(field(view.target, 'All-day reminder time'), '12:34');
		toggle(view.target, 'Pause reminders on this device');
		click(view.target, 'Enroll this device');
		await settled(view.target, saved);
		expect(view.target.textContent).toContain('Status: Active');
		expect(field(view.target, 'Device time zone (IANA)').value).toBe('Pacific/Kiritimati');
		expect(field(view.target, 'Confirm time zone change for all enrolled rooms').checked).toBe(
			true
		);
		expect(field(view.target, 'All-day reminder time').value).toBe('12:34');
		expect(field(view.target, 'Pause reminders on this device').checked).toBe(true);
		expect(fixture.writes()).toEqual([
			{
				method: 'POST',
				path: 'enrollment',
				raw: expect.any(String),
				body: {
					op_id: expect.any(String),
					base_revision: null,
					mode: 'daily_summary',
					summary_time: '09:00'
				}
			}
		]);
		expect(
			fixture.requests.filter(
				(request) => request.path === 'preferences/device' && request.method === 'GET'
			)
		).toHaveLength(2);
		expect(fixture.server.device).toEqual(defaultDevice());
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await fixture.cleanup();
	}
});
