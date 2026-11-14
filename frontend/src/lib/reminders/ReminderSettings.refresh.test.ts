// @vitest-environment happy-dom
import { flushSync } from 'svelte';
import { expect, it, vi } from 'vitest';
import { json, waitFor } from '#lib/data/test-helpers.ts';
import { button, click, fill } from '#lib/test-support/dom.ts';
import {
	activeEnrollment,
	defaultDevice,
	field,
	reminderFixture,
	reminderPolicy,
	settled,
	toggle
} from '#lib/test-support/reminder-fixture.ts';

const saved = 'Saved on this device.';
function editor(target: ParentNode): HTMLDialogElement {
	const dialog = [...target.querySelectorAll('dialog')].find(
		(node) => node.querySelector('h2')?.textContent === 'Personal room reminders'
	);
	expect(dialog).toBeDefined();
	return dialog!;
}
async function openRules(target: ParentNode): Promise<HTMLDialogElement> {
	click(target, 'Edit custom room rules');
	const dialog = editor(target);
	await settled(dialog, 'Choose your own reminder rules');
	return dialog;
}

// happy-dom does not implement Svelte's native option:checked selection.
// Seed modes through real API-shaped snapshots. Never fake select handlers.
// Native quiet/scheduled/custom transitions stay in the paused browser cases.
it('hidden blank summary does not block scheduled save and quiet resume sends saved time', async () => {
	const fixture = await reminderFixture({
		enrollment: activeEnrollment({ state: 'opted_out', mode: 'quiet', revision: 2 })
	});
	fixture.server.handle = (request) => {
		if (request.path === 'enrollment' && request.method === 'POST') {
			fixture.server.enrollment = activeEnrollment({ mode: 'quiet', revision: 3 });
			return json(200, { enrollment: fixture.server.enrollment });
		}
		if (request.path === 'preferences' && request.method === 'PATCH') {
			fixture.server.enrollment = activeEnrollment({
				mode: request.body.mode as 'scheduled' | 'daily_summary',
				revision: 3,
				summary_time: String(request.body.summary_time)
			});
			return json(200, { enrollment: fixture.server.enrollment });
		}
	};
	const quiet = fixture.view('settings');
	try {
		await quiet.loaded();
		expect(quiet.target.textContent).not.toContain('Room summary time');
		click(quiet.target, 'Resume this room');
		await settled(quiet.target, saved);
		expect(quiet.target.textContent).toContain('Status: Active');
		expect(fixture.writes()[0].body).toEqual({
			op_id: expect.any(String),
			base_revision: 2,
			mode: 'quiet',
			summary_time: '09:00'
		});
		await quiet.destroy();
		fixture.server.enrollment = activeEnrollment({ mode: 'custom' });
		const withSummary = reminderPolicy('room', { summary_enabled: true });
		fixture.server.policy = { policy: withSummary, effective: withSummary };
		const scheduled = fixture.view('settings');
		await scheduled.loaded();
		fill(field(scheduled.target, 'Room summary time'), '');
		const rules = await openRules(scheduled.target);
		// A concurrent policy save can change mode while the editor is open.
		// The real close/refresh keeps the invalid local summary, now hidden.
		fixture.server.enrollment = activeEnrollment({ mode: 'scheduled', revision: 2 });
		click(rules, 'Close');
		await scheduled.loaded();
		expect(field<HTMLSelectElement>(scheduled.target, 'Room reminder mode').value).toBe(
			'scheduled'
		);
		expect(scheduled.target.textContent).not.toContain('Room summary time');
		click(scheduled.target, 'Save room settings');
		await settled(scheduled.target, saved);
		expect(scheduled.target.querySelector('[role="alert"]')).toBeNull();
		expect(fixture.writes()[1].body).toEqual({
			op_id: expect.any(String),
			base_revision: 2,
			mode: 'scheduled',
			summary_time: '09:00'
		});
		await scheduled.destroy();
		fixture.server.enrollment = activeEnrollment({ mode: 'daily_summary', revision: 3 });
		const daily = fixture.view('settings');
		await daily.loaded();
		fill(field(daily.target, 'Room summary time'), '11:30');
		click(daily.target, 'Save room settings');
		await settled(daily.target, saved);
		expect(fixture.writes()[2].body).toEqual({
			op_id: expect.any(String),
			base_revision: 3,
			mode: 'daily_summary',
			summary_time: '11:30'
		});
	} finally {
		await fixture.cleanup();
	}
});

it('failed policy-close refresh blocks Save until retry succeeds', async () => {
	const fixture = await reminderFixture({ enrollment: activeEnrollment({ mode: 'custom' }) });
	let failRefresh = false;
	fixture.server.handle = (request) => {
		if (request.path === 'policy' && request.method === 'PUT') {
			const policy = reminderPolicy('room', { summary_enabled: true, revision: 2 });
			fixture.server.policy = { policy, effective: policy };
			return json(200, fixture.server.policy);
		}
		if (request.path === 'preferences' && request.method === 'GET' && failRefresh)
			return json(503, { error: { code: 'internal_error', message: 'Refresh unavailable' } });
		if (request.path === 'preferences' && request.method === 'PATCH') {
			fixture.server.enrollment = activeEnrollment({ mode: 'custom', revision: 2 });
			return json(200, { enrollment: fixture.server.enrollment });
		}
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		fill(field(view.target, 'All-day reminder time'), '14:25');
		const rules = await openRules(view.target);
		toggle(rules, 'Include daily summary');
		click(rules, 'Save policy');
		await settled(rules, saved);
		failRefresh = true;
		click(rules, 'Close');
		await view.loaded();
		expect(view.target.textContent).toContain(
			'Could not refresh room settings after editing rules. Your drafts are kept.'
		);
		expect(view.target.querySelectorAll('dialog')).toHaveLength(1);
		expect(button(view.target, 'Save room settings').disabled).toBe(true);
		expect(button(view.target, 'Save device settings').disabled).toBe(true);
		expect(field(view.target, 'All-day reminder time').value).toBe('14:25');
		expect(fixture.writes().map((r) => r.path)).toEqual(['policy']);
		failRefresh = false;
		click(view.target, 'Retry room settings refresh');
		await view.loaded();
		expect(view.target.querySelector('[role="alert"]')).toBeNull();
		expect(field(view.target, 'Room summary time').value).toBe('09:00');
		expect(button(view.target, 'Save room settings').disabled).toBe(false);
		click(view.target, 'Save room settings');
		await settled(view.target, saved);
		expect(fixture.writes()[1].body).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			mode: 'custom',
			summary_time: '09:00'
		});
		expect(field(view.target, 'All-day reminder time').value).toBe('14:25');
	} finally {
		await fixture.cleanup();
	}
});

it.each([false, true])(
	'policy refresh adopts clean summary but conflicts on dirty summary: dirty=%s',
	async (dirty) => {
		const fixture = await reminderFixture({ enrollment: activeEnrollment({ mode: 'custom' }) });
		const policy = reminderPolicy('room', { summary_enabled: true });
		fixture.server.policy = { policy, effective: policy };
		fixture.server.handle = (request) => {
			if (request.path === 'preferences' && request.method === 'PATCH') {
				fixture.server.enrollment = activeEnrollment({
					mode: 'custom',
					revision: 3,
					summary_time: String(request.body.summary_time)
				});
				return json(200, { enrollment: fixture.server.enrollment });
			}
		};
		const view = fixture.view('settings');
		try {
			await view.loaded();
			fill(field(view.target, 'All-day reminder time'), '14:25');
			if (dirty) fill(field(view.target, 'Room summary time'), '11:15');
			const rules = await openRules(view.target);
			fixture.server.enrollment = activeEnrollment({
				mode: 'custom',
				revision: 2,
				summary_time: '16:30'
			});
			click(rules, 'Close');
			await view.loaded();
			expect(field(view.target, 'Room summary time').value).toBe(dirty ? '11:15' : '16:30');
			expect(view.target.querySelector('fieldset')!.disabled).toBe(dirty);
			expect(field(view.target, 'All-day reminder time').value).toBe('14:25');
			if (dirty) {
				expect(view.target.textContent).toContain(
					'Room settings changed elsewhere. Load latest revisions and review your edits.'
				);
				expect(field(view.target, 'Room summary time').closest('fieldset')!.disabled).toBe(true);
				expect(button(view.target, 'Load latest revisions').disabled).toBe(false);
				expect(fixture.writes()).toHaveLength(0);
			} else {
				expect(view.target.querySelector('[role="alert"]')).toBeNull();
				expect(button(view.target, 'Save room settings').disabled).toBe(false);
				click(view.target, 'Save room settings');
				await settled(view.target, saved);
				expect(fixture.writes()[0].body).toEqual({
					op_id: expect.any(String),
					base_revision: 2,
					mode: 'custom',
					summary_time: '16:30'
				});
			}
			expect(fixture.server.enrollment).toMatchObject({ summary_time: '16:30' });
			expect(field(view.target, 'All-day reminder time').value).toBe('14:25');
			expect(fixture.writes().every((r) => r.path === 'preferences')).toBe(true);
		} finally {
			await fixture.cleanup();
		}
	}
);

it('mode-save policy refresh failure uses visible fallback and retry', async () => {
	const fixture = await reminderFixture({ enrollment: activeEnrollment({ mode: 'custom' }) });
	let failPolicy = false;
	fixture.server.handle = (request) => {
		if (request.path === 'preferences' && request.method === 'PATCH') {
			fixture.server.enrollment = activeEnrollment({ mode: 'custom', revision: 2 });
			failPolicy = true;
			return json(200, { enrollment: fixture.server.enrollment });
		}
		if (request.path === 'policy' && request.method === 'GET' && failPolicy)
			return json(503, {
				error: { code: 'internal_error', message: 'Policy unavailable after save' }
			});
	};
	const view = fixture.view('settings');
	try {
		await view.loaded();
		expect(view.target.textContent).not.toContain('Room summary time');
		click(view.target, 'Save room settings');
		await settled(view.target, saved);
		expect(view.target.textContent).toContain(
			'Could not check whether the custom policy includes a summary.'
		);
		expect(field(view.target, 'Room summary time').value).toBe('09:00');
		expect(fixture.requests.filter((r) => r.path === 'policy' && r.method === 'GET')).toHaveLength(
			2
		);
		expect(fixture.writes()[0].body).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			mode: 'custom',
			summary_time: '09:00'
		});
		failPolicy = false;
		click(view.target, 'Retry custom summary check');
		await waitFor(() => {
			flushSync();
			expect(view.target.querySelector('[role="alert"]')).toBeNull();
		});
		expect(view.target.textContent).not.toContain('Room summary time');
		expect(view.target.textContent).not.toContain('Retry custom summary check');
		expect(fixture.requests.filter((r) => r.path === 'policy' && r.method === 'GET')).toHaveLength(
			3
		);
		expect(fixture.writes()).toHaveLength(1);
	} finally {
		await fixture.cleanup();
	}
});

it('Oslo text time controls and custom editor entry', async () => {
	const fixture = await reminderFixture({
		enrollment: { state: 'not_enrolled', revision: null },
		device: null
	});
	vi.spyOn(navigator, 'language', 'get').mockReturnValue('en-US');
	vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['en-US']);
	fixture.server.handle = (request) => {
		if (request.path === 'enrollment' && request.method === 'POST') {
			fixture.server.enrollment = activeEnrollment({ summary_time: '13:45' });
			fixture.server.device = defaultDevice();
			return json(200, { enrollment: fixture.server.enrollment });
		}
		if (request.path === 'preferences' && request.method === 'PATCH') {
			fixture.server.enrollment = activeEnrollment({
				mode: 'custom',
				revision: 2,
				summary_time: '13:45'
			});
			return json(200, { enrollment: fixture.server.enrollment });
		}
	};
	const first = fixture.view('settings');
	try {
		await first.loaded();
		expect(navigator.language).toBe('en-US');
		expect(first.target.textContent).toContain('Time zone: Europe/Oslo');
		const summary = field(first.target, 'Room summary time');
		expect(summary.type).toBe('text');
		expect(summary.inputMode).toBe('text');
		expect(summary.placeholder).toBe('HH:MM');
		fill(summary, '13:45');
		click(first.target, 'Enroll this device');
		await settled(first.target, saved);
		expect(first.target.textContent).toContain('Status: Active');
		expect(first.target.textContent).toContain('Device time zone: Europe/Oslo');
		for (const label of [
			'Room summary time',
			'All-day reminder time',
			'Quiet hours start',
			'Quiet hours end'
		]) {
			expect(field(first.target, label).type).toBe('text');
			expect(field(first.target, label).inputMode).toBe('text');
		}
		expect(fixture.writes()[0].body).toEqual({
			op_id: expect.any(String),
			base_revision: null,
			timezone: 'Europe/Oslo',
			mode: 'daily_summary',
			summary_time: '13:45'
		});
		await first.destroy();
		fixture.server.enrollment = activeEnrollment({ mode: 'quiet', summary_time: '13:45' });
		const quiet = fixture.view('settings');
		await quiet.loaded();
		expect(quiet.target.textContent).not.toContain('Room summary time');
		await quiet.destroy();
		fixture.server.enrollment = activeEnrollment({ mode: 'custom', summary_time: '13:45' });
		const custom = fixture.view('settings');
		await custom.loaded();
		click(custom.target, 'Save room settings');
		await settled(custom.target, saved);
		expect(fixture.writes()[1].body).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			mode: 'custom',
			summary_time: '13:45'
		});
		const rules = await openRules(custom.target);
		expect(button(rules, 'Add relative rule').disabled).toBe(false);
	} finally {
		await fixture.cleanup();
	}
});
