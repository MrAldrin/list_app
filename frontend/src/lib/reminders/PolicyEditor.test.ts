// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { makeFeed, makeItem, makeList, json, waitFor } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button, click, fill } from '#lib/test-support/dom.ts';
import PolicyEditor from './PolicyEditor.svelte';
import type { Policy, PolicyResult, Preview } from './api';
import {
	field,
	network,
	reminderFixture,
	reminderPolicy,
	settled
} from '#lib/test-support/reminder-fixture.ts';

it('fixed save confirmation identity and explicit conflict reload retain wall draft', async () => {
	const firstId = '11111111-1111-4111-8111-111111111111';
	const secondId = '22222222-2222-4222-8222-222222222222';
	const thirdId = '33333333-3333-4333-8333-333333333333';
	const initial: Policy = {
		scope: 'item',
		state: 'replace',
		preset: 'custom',
		summary_enabled: false,
		rules: [],
		revision: 1,
		activated_at: '2035-01-01T00:00:00Z'
	};
	let current: PolicyResult = { policy: initial, effective: initial };
	const writes: Record<string, unknown>[] = [];
	const list = makeList();
	const milk = makeItem(list.uid);
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	const path = `/api/v1/rooms/${fixture.room.slug}/reminders/items/${milk.uid}/policy`;
	const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		expect(input).toBe(path);
		expect(init?.credentials).toBe('same-origin');
		if (init?.method === 'GET') return json(200, current);
		expect(init?.method).toBe('PUT');
		const body = JSON.parse(String(init?.body));
		writes.push(body);
		if (writes.length === 5)
			return json(409, {
				error: { code: 'revision_conflict', message: 'Changed elsewhere' }
			});
		const time = writes.length < 3 ? '12:00' : writes.length <= 4 ? '13:00' : '14:00';
		const policy: Policy = {
			scope: 'item',
			state: 'replace',
			preset: 'custom',
			summary_enabled: false,
			revision: writes.length + 1,
			activated_at: '2035-01-01T00:00:00Z',
			rules: [
				{
					kind: 'fixed',
					id: writes.length < 3 ? firstId : writes.length <= 4 ? secondId : thirdId,
					date: '2040-06-01',
					time,
					timezone: 'UTC',
					instant: `2040-06-01T${time}:00Z`,
					activation: '2035-01-01T00:00:00Z'
				}
			]
		};
		current = { policy, effective: policy };
		return json(200, current);
	});
	vi.stubGlobal('fetch', fetch);
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(PolicyEditor, {
		target,
		props: { room: fixture.room, scope: 'item', uid: milk.uid, onClose: vi.fn() }
	});
	const input = (label: string): HTMLInputElement => {
		const node = [...target.querySelectorAll('label')].find(
			(node) => node.textContent?.trim() === label
		);
		expect(node, `label ${label}`).toBeDefined();
		const field = node!.querySelector('input');
		expect(field, `input ${label}`).not.toBeNull();
		return field!;
	};
	const save = async (count: number) => {
		click(target, 'Save policy');
		await waitFor(() => {
			flushSync();
			expect(writes).toHaveLength(count);
			expect(target.textContent).toContain('Saved on this device.');
		});
	};
	try {
		await waitFor(() => {
			flushSync();
			expect(target.textContent).not.toContain('Loading…');
		});
		// Happy-dom does not match option:checked, which Svelte uses for select
		// changes. Start with a server-loaded Custom policy; keep native selection
		// in the browser journey rather than replacing that browser capability.
		click(target, 'Add fixed wall time');
		fill(input('Wall date'), '2040-06-01');
		expect(input('Wall time').getAttribute('inputmode')).toBe('text');
		fill(input('Wall time'), '12:00');
		fill(input('Time zone'), 'UTC');
		expect(target.textContent).not.toContain('Confirmed UTC:');
		await save(1);
		expect(writes[0]).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			state: 'replace',
			preset: 'custom',
			summary_enabled: false,
			rules: [{ kind: 'fixed', date: '2040-06-01', time: '12:00', timezone: 'UTC' }]
		});
		expect(target.textContent).toContain('Confirmed UTC: 2040-06-01T12:00:00Z');
		await save(2);
		expect(writes[1]).toMatchObject({
			base_revision: 2,
			rules: [{ kind: 'fixed', id: firstId, date: '2040-06-01', time: '12:00', timezone: 'UTC' }]
		});
		expect(current.policy.rules[0]).toMatchObject({ id: firstId });
		fill(input('Wall time'), '13:00');
		expect(target.textContent).not.toContain('Confirmed UTC:');
		await save(3);
		expect(writes[2]).toMatchObject({
			base_revision: 3,
			rules: [{ kind: 'fixed', time: '13:00', timezone: 'UTC' }]
		});
		expect((writes[2].rules as Record<string, unknown>[])[0]).not.toHaveProperty('id');
		expect(current.policy.rules[0]).toMatchObject({ id: secondId });
		expect(target.textContent).toContain('Confirmed UTC: 2040-06-01T13:00:00Z');
		await save(4);
		expect(writes[3]).toMatchObject({
			base_revision: 4,
			rules: [{ kind: 'fixed', id: secondId, time: '13:00' }]
		});
		const external: Policy = { ...initial, state: 'off', preset: null, revision: 6 };
		current = { policy: external, effective: external };
		fill(input('Wall time'), '14:00');
		click(target, 'Save policy');
		await waitFor(() => {
			flushSync();
			expect(target.textContent).toContain(
				'Changed elsewhere. Load the latest revision and review your draft.'
			);
		});
		expect(writes).toHaveLength(5);
		expect(writes[4]).toMatchObject({ base_revision: 5, rules: [{ time: '14:00' }] });
		const readsBeforeReload = fetch.mock.calls.filter(([, init]) => init?.method === 'GET').length;
		expect(readsBeforeReload).toBe(1);
		expect(input('Wall time').value).toBe('14:00');
		click(target, 'Load latest revision');
		await waitFor(() => {
			flushSync();
			expect(target.textContent).toContain(
				'Latest revision loaded. Your draft is unchanged; review it before saving.'
			);
		});
		expect(fetch.mock.calls.filter(([, init]) => init?.method === 'GET')).toHaveLength(2);
		expect(input('Wall time').value).toBe('14:00');
		expect(target.textContent).toContain('Effective source: item; off.');
		expect(button(target, 'Save policy').disabled).toBe(false);
		await save(6);
		expect(writes[5]).toMatchObject({
			base_revision: 6,
			state: 'replace',
			preset: 'custom',
			rules: [{ time: '14:00' }]
		});
		expect((writes[5].rules as Record<string, unknown>[])[0]).not.toHaveProperty('id');
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
		vi.unstubAllGlobals();
	}
});

// Native select transitions remain in the paused browser tests. Seed each
// API-shaped branch rather than patching happy-dom's missing option:checked.
it.each(['off', 'inherit'] as const)(
	'list %s policy saves exact state and renders effective source',
	async (state) => {
		const fixture = await reminderFixture();
		const policy = reminderPolicy('list', { state, preset: null, revision: 2 });
		const effective =
			state === 'inherit' ? reminderPolicy('room', { preset: 'scheduled' }) : policy;
		fixture.server.policy = { policy, effective };
		fixture.server.handle = (request) =>
			request.method === 'PUT'
				? json(200, { policy: { ...policy, revision: 3 }, effective })
				: undefined;
		const view = fixture.view('list');
		try {
			await view.loaded();
			expect(field<HTMLSelectElement>(view.target, 'Policy').value).toBe(state);
			expect(view.target.textContent).toContain(
				`Effective source: ${effective.scope}; ${effective.state}`
			);
			click(view.target, 'Save policy');
			await settled(view.target, 'Saved on this device.');
			expect(view.target.textContent).toContain(
				`Effective source: ${effective.scope}; ${effective.state}`
			);
			expect(fixture.writes()).toEqual([
				{
					method: 'PUT',
					path: `lists/${fixture.list.uid}/policy`,
					raw: expect.any(String),
					body: { op_id: expect.any(String), base_revision: 2, state }
				}
			]);
			expect(fixture.api.sendOp).not.toHaveBeenCalled();
		} finally {
			await fixture.cleanup();
		}
	}
);

it('inherit preview retry and offline draft retain the exact committed lost PUT', async () => {
	const fixture = await reminderFixture();
	const initial = reminderPolicy('item');
	fixture.server.policy = { policy: initial, effective: initial };
	const committed = reminderPolicy('item', {
		revision: 2,
		rules: [{ kind: 'relative', basis: 'calendar', amount: 1, key: 'calendar:1d' }]
	});
	let attempts = 0;
	fixture.server.handle = (request) => {
		if (request.path === 'preview')
			return json(200, {
				source: 'item',
				state: 'replace',
				preset: 'custom',
				timezone: 'Europe/Oslo',
				disabled_reasons: [],
				provisional_fixed_ids: [],
				entries: []
			});
		if (request.method === 'PUT') {
			fixture.server.policy = { policy: committed, effective: committed };
			if (++attempts === 1) throw new TypeError('connection lost after commit');
			return json(200, fixture.server.policy);
		}
	};
	const view = fixture.view('item');
	try {
		await view.loaded();
		click(view.target, 'Add relative rule');
		click(view.target, 'Preview next five');
		await settled(view.target, 'Preview: item policy');
		expect(fixture.writes()[0]).toMatchObject({
			method: 'POST',
			path: 'preview',
			body: {
				item_uid: fixture.item.uid,
				draft: {
					state: 'replace',
					preset: 'custom',
					summary_enabled: false,
					rules: [{ kind: 'relative', amount: 1, unit: 'days' }]
				}
			}
		});
		click(view.target, 'Save policy');
		await settled(view.target, 'Result unknown. Retry the unchanged request; your draft is kept.');
		expect(attempts).toBe(1);
		expect(fixture.server.policy.policy.revision).toBe(2);
		expect(field(view.target, 'Amount before due').closest('fieldset')!.disabled).toBe(true);
		expect(button(view.target, 'Close').disabled).toBe(true);
		click(view.target, 'Retry request');
		await settled(view.target, 'Saved on this device.');
		const puts = fixture.writes().filter((request) => request.method === 'PUT');
		expect(puts).toHaveLength(2);
		expect(puts[1]).toEqual(puts[0]);
		expect(puts[0].body).toEqual({
			op_id: expect.any(String),
			base_revision: 1,
			state: 'replace',
			preset: 'custom',
			summary_enabled: false,
			rules: [{ kind: 'relative', amount: 1, unit: 'days' }]
		});
		expect(field(view.target, 'Amount before due').value).toBe('1');
		network(false);
		expect(button(view.target, 'Save policy').disabled).toBe(true);
		expect(button(view.target, 'Preview next five').disabled).toBe(true);
		expect(field(view.target, 'Amount before due').value).toBe('1');
		expect(fixture.writes()).toHaveLength(3);
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await fixture.cleanup();
	}
});

it('same-instant rule and summary both render and preview can refresh', async () => {
	const fixture = await reminderFixture();
	const policy = reminderPolicy('item', { summary_enabled: true });
	fixture.server.policy = { policy, effective: policy };
	const collision = '2040-06-01T09:00:00Z';
	let previews = 0;
	fixture.server.handle = (request) => {
		if (request.path !== 'preview') return;
		const result: Preview = {
			source: 'item',
			state: 'replace',
			preset: 'custom',
			timezone: 'UTC',
			disabled_reasons: [],
			provisional_fixed_ids: [],
			entries: [
				{
					kind: 'rules',
					instant: ++previews === 1 ? collision : '2040-05-31T09:00:00Z',
					keys: ['at-due'],
					deferred_until: null,
					local_day: null
				},
				{
					kind: 'summary',
					instant: collision,
					keys: [],
					deferred_until: null,
					local_day: '2040-06-01'
				}
			]
		};
		return json(200, result);
	};
	const view = fixture.view('item');
	try {
		await view.loaded();
		click(view.target, 'Add relative rule');
		fill(field(view.target, 'Amount before due'), '0');
		click(view.target, 'Preview next five');
		await waitFor(() => {
			flushSync();
			expect(button(view.target, 'Preview next five').disabled).toBe(false);
		});
		expect([...view.target.querySelectorAll('li')].map((li) => li.textContent?.trim())).toEqual([
			`rules: original UTC ${collision}`,
			`summary: original UTC ${collision}; summary day 2040-06-01`
		]);
		expect(view.target.querySelector('[role="alert"]')).toBeNull();
		fill(field(view.target, 'Amount before due'), '1');
		expect(view.target.querySelector('li')).toBeNull();
		click(view.target, 'Preview next five');
		await settled(view.target, 'rules: original UTC 2040-05-31T09:00:00Z');
		expect(view.target.querySelectorAll('li')).toHaveLength(2);
		expect(view.target.textContent).toContain(`summary: original UTC ${collision}`);
		expect(view.target.querySelector('[role="alert"]')).toBeNull();
		expect(fixture.writes().map((request) => request.body)).toEqual(
			[0, 1].map((amount) => ({
				item_uid: fixture.item.uid,
				draft: {
					state: 'replace',
					preset: 'custom',
					summary_enabled: true,
					rules: [{ kind: 'relative', amount, unit: 'days' }]
				}
			}))
		);
	} finally {
		await fixture.cleanup();
	}
});
