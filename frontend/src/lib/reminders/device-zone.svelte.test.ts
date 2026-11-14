// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { makeFeed, makeItem, makeList, json, waitFor } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button, click, fill } from '#lib/test-support/dom.ts';
import RoomHeader from '#lib/room/RoomHeader.svelte';
import ListView from '#lib/list/ListView.svelte';
import { advanceDueClock, dueClock } from '#lib/list/due-clock.svelte.ts';
import ReminderSettings from './ReminderSettings.svelte';
import { deviceZone } from './device-zone.svelte';
import type { Device, Policy } from './api';

vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost/room/home-ab12cd') } }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

it('saved zone invalidates due subscribers', async () => {
	const previousNow = dueClock.now;
	vi.setSystemTime(new Date('2035-01-01T23:30:00Z'));
	advanceDueClock(new Date());
	let device: Device = {
		revision: 1,
		timezone: 'UTC',
		all_day_time: '09:00',
		paused: false,
		quiet_hours: null,
		daily_cap: 10,
		spacing_minutes: 10,
		content_privacy: 'generic',
		overdue_repeat_days: null
	};
	const policy: Policy = {
		scope: 'room',
		state: 'replace',
		preset: 'daily_summary',
		summary_enabled: true,
		rules: [],
		revision: 1,
		activated_at: '2035-01-01T00:00:00Z'
	};
	const writes: Record<string, unknown>[] = [];
	const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		const path = String(input);
		expect(init?.credentials).toBe('same-origin');
		if (path.endsWith('/preferences/device')) {
			if (init?.method === 'PATCH') {
				writes.push(JSON.parse(String(init.body)));
				device = { ...device, revision: 2, timezone: 'Pacific/Kiritimati' };
			}
			return json(200, { device });
		}
		if (path.endsWith('/preferences') && init?.method === 'GET')
			return json(200, {
				enrollment: {
					state: 'active',
					mode: 'daily_summary',
					summary_time: '09:00',
					revision: 1,
					activated_at: '2035-01-01T00:00:00Z'
				}
			});
		if (path.endsWith('/policy') && init?.method === 'GET')
			return json(200, { policy, effective: policy });
		throw new Error(`Unexpected ${init?.method} ${path}`);
	});
	vi.stubGlobal('fetch', fetch);
	const list = makeList();
	const fixture = await readyRoom(
		makeFeed({
			full: true,
			lists: [list],
			items: [makeItem(list.uid, { date: '2035-01-02' })]
		})
	);
	const roomTarget = document.createElement('div');
	const listTarget = document.createElement('div');
	const settingsTarget = document.createElement('div');
	document.body.append(roomTarget, listTarget, settingsTarget);
	const roomView = mount(RoomHeader, {
		target: roomTarget,
		props: { room: fixture.room, onLogout: vi.fn() }
	});
	const listView = mount(ListView, {
		target: listTarget,
		props: {
			room: fixture.room,
			list,
			roomHref: '/room/home-ab12cd',
			canReset: false,
			roomDue: true
		}
	});
	const settings = mount(ReminderSettings, {
		target: settingsTarget,
		props: { room: fixture.room, onClose: vi.fn() }
	});
	try {
		await waitFor(() => {
			flushSync();
			expect(deviceZone(fixture.room)).toBe('UTC');
			expect(settingsTarget.textContent).not.toContain('Loading settings…');
		});
		expect(listTarget.querySelector('.row .due')?.textContent).toBe('Tomorrow');
		for (const target of [roomTarget, listTarget]) {
			click(target, 'Due items: 1 due, 0 overdue');
			expect(target.querySelector('dialog h3')?.textContent).toContain('Tomorrow');
			expect(target.querySelector('dialog .due-row .name')?.textContent).toBe('milk');
		}
		const zoneLabel = [...settingsTarget.querySelectorAll('label')].find(
			(label) => label.textContent === 'Device time zone (IANA)'
		)!;
		expect(zoneLabel).toBeDefined();
		fill(
			settingsTarget.querySelector<HTMLInputElement>(`#${zoneLabel.htmlFor}`)!,
			'Pacific/Kiritimati'
		);
		const confirm = [...settingsTarget.querySelectorAll('label')]
			.find((label) => label.textContent?.includes('Confirm time zone change'))!
			.querySelector('input')!;
		confirm.click();
		flushSync();
		expect(button(settingsTarget, 'Save device settings').disabled).toBe(false);
		click(settingsTarget, 'Save device settings');
		await waitFor(() => {
			flushSync();
			expect(settingsTarget.textContent).toContain('Saved on this device.');
		});
		expect(writes).toEqual([
			{
				op_id: expect.any(String),
				base_revision: 1,
				timezone: 'Pacific/Kiritimati',
				all_day_time: '09:00',
				paused: false,
				quiet_hours: null,
				daily_cap: 10,
				spacing_minutes: 10,
				content_privacy: 'generic',
				overdue_repeat_days: null
			}
		]);
		expect(deviceZone(fixture.room)).toBe('Pacific/Kiritimati');
		expect(listTarget.querySelector('.row .due')?.textContent).toBe('Today');
		for (const target of [roomTarget, listTarget]) {
			expect(target.querySelector('dialog h3')?.textContent).toContain('Today');
			expect(target.querySelector('dialog')?.textContent).not.toContain('Tomorrow');
			expect(target.querySelector('dialog .due-row .name')?.textContent).toBe('milk');
		}
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(settings);
		await unmount(listView);
		await unmount(roomView);
		fixture.room.release();
		roomTarget.remove();
		listTarget.remove();
		settingsTarget.remove();
		localStorage.clear();
		vi.unstubAllGlobals();
		vi.useRealTimers();
		advanceDueClock(previousNow);
	}
});
