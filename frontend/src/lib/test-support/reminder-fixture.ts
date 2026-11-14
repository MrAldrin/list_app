// Real reminder components and RoomHandle; only the HTTP/storage edges are replaced.
import { flushSync, mount, unmount } from 'svelte';
import { expect, vi } from 'vitest';
import { json, makeFeed, makeItem, makeList, waitFor } from '#lib/data/test-helpers.ts';
import type { Device, Enrollment, Policy, PolicyResult, PolicyScope } from '#lib/reminders/api.ts';
import PolicyEditor from '#lib/reminders/PolicyEditor.svelte';
import ReminderSettings from '#lib/reminders/ReminderSettings.svelte';
import { readyRoom } from './room-fixture';

export const activation = '2035-01-01T00:00:00Z';
export function activeEnrollment(
	overrides: Partial<Extract<Enrollment, { state: 'active' | 'needs_resume' | 'opted_out' }>> = {}
): Enrollment {
	return {
		state: 'active',
		mode: 'daily_summary',
		summary_time: '09:00',
		revision: 1,
		activated_at: activation,
		...overrides
	};
}
export function defaultDevice(overrides: Partial<Device> = {}): Device {
	return {
		revision: 1,
		timezone: 'Europe/Oslo',
		all_day_time: '09:00',
		paused: false,
		quiet_hours: { start: '22:00', end: '08:00' },
		daily_cap: 10,
		spacing_minutes: 10,
		content_privacy: 'generic',
		overdue_repeat_days: null,
		...overrides
	};
}
export function reminderPolicy(scope: PolicyScope, overrides: Partial<Policy> = {}): Policy {
	return {
		scope,
		state: 'replace',
		preset: 'custom',
		summary_enabled: false,
		rules: [],
		revision: 1,
		activated_at: activation,
		...overrides
	};
}
export interface ReminderRequest {
	method: string;
	path: string;
	raw: string | null;
	body: Record<string, unknown>;
}
export async function reminderFixture(
	options: { enrollment?: Enrollment; device?: Device | null; slug?: string } = {}
) {
	const list = makeList();
	const item = makeItem(list.uid);
	const initial = makeFeed({ full: true, lists: [list], items: [item] });
	if (options.slug) initial.room = { ...initial.room!, slug: options.slug };
	const fixture = await readyRoom(initial);
	const base = `/api/v1/rooms/${fixture.room.slug}/reminders/`;
	const requests: ReminderRequest[] = [];
	const server = {
		enrollment: options.enrollment ?? activeEnrollment(),
		device: options.device === undefined ? defaultDevice() : options.device,
		policy: { policy: reminderPolicy('room'), effective: reminderPolicy('room') } as PolicyResult,
		handle: undefined as
			| ((request: ReminderRequest) => Promise<Response | undefined> | Response | undefined)
			| undefined
	};
	const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		expect(String(input).startsWith(base), 'room-owned reminder URL').toBe(true);
		expect(init?.credentials).toBe('same-origin');
		const request: ReminderRequest = {
			method: init?.method ?? 'GET',
			path: String(input).slice(base.length),
			raw: init?.body == null ? null : String(init.body),
			body: init?.body == null ? {} : JSON.parse(String(init.body))
		};
		requests.push(request);
		const answer = await server.handle?.(request);
		if (answer) return answer;
		if (request.method === 'GET') {
			if (request.path === 'preferences') return json(200, { enrollment: server.enrollment });
			if (request.path === 'preferences/device') return json(200, { device: server.device });
			if (request.path.endsWith('policy')) return json(200, server.policy);
		}
		throw new Error(`Unexpected ${request.method} ${request.path}`);
	});
	vi.stubGlobal('fetch', fetch);
	const views: { destroy: () => Promise<void> }[] = [];
	function view(kind: 'settings' | PolicyScope, onClose = vi.fn()) {
		const target = document.createElement('div');
		document.body.append(target);
		const component =
			kind === 'settings'
				? mount(ReminderSettings, { target, props: { room: fixture.room, onClose } })
				: mount(PolicyEditor, {
						target,
						props: {
							room: fixture.room,
							scope: kind,
							uid: kind === 'item' ? item.uid : kind === 'list' ? list.uid : undefined,
							onClose
						}
					});
		let destroyed = false;
		const result = {
			target,
			onClose,
			async loaded() {
				await waitFor(() => {
					flushSync();
					expect(target.textContent).not.toContain('Loading');
					expect(target.querySelector('fieldset')).not.toBeNull();
				});
			},
			async destroy() {
				if (!destroyed) {
					destroyed = true;
					await unmount(component);
					target.remove();
				}
			}
		};
		views.push(result);
		return result;
	}
	return {
		...fixture,
		list,
		item,
		server,
		requests,
		fetch,
		view,
		writes: () => requests.filter((request) => request.method !== 'GET'),
		async cleanup() {
			for (const view of views.reverse()) await view.destroy();
			fixture.room.release();
			vi.unstubAllGlobals();
			vi.restoreAllMocks();
		}
	};
}

export function field<T extends HTMLInputElement | HTMLSelectElement = HTMLInputElement>(
	target: ParentNode,
	label: string
): T {
	const node = [...target.querySelectorAll('label')].find((node) => {
		const copy = node.cloneNode(true) as HTMLLabelElement;
		for (const control of copy.querySelectorAll('input,select')) control.remove();
		return copy.textContent?.replace(/\s+/g, ' ').trim() === label;
	});
	expect(node, `label ${label}`).toBeDefined();
	const control = node!.htmlFor
		? document.getElementById(node!.htmlFor)
		: node!.querySelector('input,select');
	expect(control, `control ${label}`).not.toBeNull();
	return control as T;
}
export function toggle(target: ParentNode, label: string): void {
	field(target, label).click();
	flushSync();
}
export async function settled(target: ParentNode, text: string): Promise<void> {
	await waitFor(() => {
		flushSync();
		expect(target.textContent).toContain(text);
	});
}
export function network(online: boolean): void {
	vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(online);
	window.dispatchEvent(new Event(online ? 'online' : 'offline'));
	flushSync();
}
