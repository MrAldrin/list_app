// @vitest-environment happy-dom
import { flushSync, mount, tick, unmount } from 'svelte';
import { page } from '$app/state';
import { afterEach, expect, it, vi } from 'vitest';
import type { Item, RoomHandle } from '#lib/data/index.ts';
import { createRoomStore } from '#lib/data/room-store.svelte.ts';
import {
	applied,
	deferred,
	makeFeed,
	makeItem,
	makeList,
	ROOM,
	waitFor
} from '#lib/data/test-helpers.ts';
import ListView from './ListView.svelte';
import ListHarness from '#lib/test-support/ListHarness.svelte';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button, click, fill, rowNames, submit } from '#lib/test-support/dom.ts';
import { toasts } from '#lib/ui/toasts.svelte.ts';
import { MemoryQueueStorage } from '#lib/data/queue-storage.ts';
import { HOLD_MS } from './hold-order.ts';
import { readyShare } from '#lib/test-support/share-fixture.ts';
import SavedViewNotice from '#lib/ui/SavedViewNotice.svelte';
import { IDBFactory } from 'fake-indexeddb';
import { createSnapshotStore } from '#lib/data/snapshot-store.ts';
import { ApiError, NetworkError } from '#lib/data/index.ts';
import { advanceDueClock, dueClock } from './due-clock.svelte.ts';

const reminderSettings = vi.hoisted(() => ({ enabled: false }));
vi.mock('#lib/reminders/personal-reminders.ts', () => ({
	get PERSONAL_REMINDER_SETTINGS_ENABLED() {
		return reminderSettings.enabled;
	}
}));

afterEach(() => {
	for (const toast of toasts.items) toasts.dismiss(toast.id);
	localStorage.clear();
	reminderSettings.enabled = false;
	Object.assign(page, { url: new URL('http://localhost/list/test') });
});

vi.mock('$app/state', async () => {
	const { reactive } = await import('#lib/test-support/reactive.svelte.ts');
	return { page: reactive({ url: new URL('http://localhost/list/test') }) };
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

it('tag filters undo duplicates and hide-all render together with real store updates and fresh-feed remount', async () => {
	let list = makeList();
	let items = ['milk', 'bread', 'apples', 'eggs'].map((name) => makeItem(list.uid, { name }));
	let seq = 1;
	const feed = () => makeFeed({ full: true, seq, lists: [list], items });
	let fixture = await readyRoom(feed());
	const fixtureHandles = [fixture.room];
	const answer = async (_slug: string, op: import('#lib/data/index.ts').SentOp) => {
		seq += 1;
		switch (op.type) {
			case 'list.tag_add':
				list = {
					...list,
					tags: [...new Set([...list.tags, op.tag])].sort((a, b) =>
						a.toLowerCase().localeCompare(b.toLowerCase())
					),
					changed_seq: seq
				};
				break;
			case 'list.tag_remove':
				list = { ...list, tags: list.tags.filter((tag) => tag !== op.tag), changed_seq: seq };
				break;
			case 'item.toggle_tag':
				items = items.map((item) =>
					item.uid === op.item_uid
						? {
								...item,
								tags: op.active
									? [...new Set([...item.tags, op.tag])]
									: item.tags.filter((tag) => tag !== op.tag),
								changed_seq: seq
							}
						: item
				);
				break;
			case 'item.set_done':
				items = items.map((item) =>
					item.uid === op.item_uid
						? {
								...item,
								done: op.done,
								changed_seq: seq,
								completed_at: op.done ? '2026-11-02T12:00:00Z' : null
							}
						: item
				);
				break;
			case 'list.visibility':
				list = {
					...list,
					hide_done: { ...list.hide_done, mode: op.mode ?? list.hide_done.mode },
					changed_seq: seq
				};
				break;
			default:
				throw new Error(`Unexpected ${op.type}`);
		}
		fixture.setFeed(feed());
		return applied(op, seq, { changed_seq: seq });
	};
	fixture.api.sendOp.mockImplementation(answer);
	const target = document.createElement('div');
	document.body.append(target);
	let component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const settled = async () => {
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
	};
	const chips = () => target.querySelector('ul.chips')!;
	const chip = (name: string) => click(chips(), name);
	const addTag = async (name: string) => {
		click(target, 'Tags');
		fill(target.querySelector('input[aria-label="Add tag"]')!, name);
		submit(target.querySelector('dialog')!);
		await settled();
		click(target.querySelector('dialog')!, 'Close');
	};
	const hideSwitch = () =>
		[...target.querySelectorAll('label')]
			.find((label) => label.textContent?.trim() === 'Hide checked-off items')!
			.querySelector('input')!;
	try {
		flushSync();
		expect(rowNames(target)).toEqual(['apples', 'bread', 'eggs', 'milk']);
		click(target, 'Options');
		await addTag(' Market ');
		await addTag('Lidl');
		expect([...chips().querySelectorAll('button')].map((n) => n.textContent?.trim())).toEqual([
			'Lidl',
			'Market'
		]);
		expect(button(target, 'Lidl tag for milk').getAttribute('aria-pressed')).toBe('false');
		for (const name of ['milk', 'eggs']) {
			click(target, `Lidl tag for ${name}`);
			await settled();
			expect(button(target, `Lidl tag for ${name}`).getAttribute('aria-pressed')).toBe('true');
		}
		await addTag('Bakery');
		for (const [tag, name] of [
			['Market', 'milk'],
			['Market', 'bread'],
			['Bakery', 'bread']
		]) {
			click(target, `${tag} tag for ${name}`);
			await settled();
			expect(button(target, `${tag} tag for ${name}`).getAttribute('aria-pressed')).toBe('true');
		}
		click(target, 'Done');
		chip('Lidl');
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('true');
		expect(rowNames(target)).toEqual(['eggs', 'milk']);
		chip('Bakery');
		expect(rowNames(target)).toEqual([]);
		expect(target.textContent).toContain('No items match all selected tags.');
		chip('Bakery');
		expect(rowNames(target)).toEqual(['eggs', 'milk']);
		expect(target.textContent).not.toContain('No items match all selected tags.');
		chip('Market');
		expect(button(chips(), 'Market').getAttribute('aria-pressed')).toBe('true');
		expect(rowNames(target)).toEqual(['milk']);
		chip('Lidl');
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('false');
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		chip('Market');
		expect(rowNames(target)).toEqual(['apples', 'bread', 'eggs', 'milk']);

		click(target, 'Options');
		chip('Lidl');
		click(target.querySelector('dialog')!, 'Delete tag');
		await settled();
		expect(target.textContent).toContain('Deleted tag Lidl');
		expect(target.querySelector('[aria-label="Lidl tag for milk"]')).toBeNull();
		click(target, 'Undo');
		await settled();
		expect(target.textContent).toContain('Restored tag Lidl');
		expect(button(target, 'Lidl tag for milk').getAttribute('aria-pressed')).toBe('true');

		click(target, 'Tags');
		const field = target.querySelector<HTMLInputElement>('input[aria-label="Add tag"]')!;
		const sends = fixture.api.sendOp.mock.calls.length;
		fill(field, 'Lidl');
		submit(target.querySelector('dialog')!);
		expect(target.textContent).toContain("'Lidl' is already a tag");
		expect(field.value).toBe('');
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(sends);
		fill(field, 'lidl');
		submit(target.querySelector('dialog')!);
		await settled();
		click(target.querySelector('dialog')!, 'Close');
		expect(button(chips(), 'lidl')).toBeDefined();
		expect(hideSwitch().checked).toBe(false);
		(target.querySelector('input[aria-label="apples"]') as HTMLInputElement).click();
		await settled();
		expect((target.querySelector('input[aria-label="apples"]') as HTMLInputElement).checked).toBe(
			true
		);
		hideSwitch().click();
		await settled();
		expect(
			(target.querySelector('input[type="radio"][value="all"]') as HTMLInputElement).checked
		).toBe(true);
		expect(rowNames(target)).toEqual(['bread', 'eggs', 'milk']);

		await unmount(component);
		fixture.room.release();
		fixture = await readyRoom(feed());
		fixtureHandles.push(fixture.room);
		fixture.api.sendOp.mockImplementation(answer);
		component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
		flushSync();
		expect(rowNames(target)).toEqual(['bread', 'eggs', 'milk']);
		click(target, 'Options');
		expect(hideSwitch().checked).toBe(true);
		hideSwitch().click();
		await settled();
		expect(rowNames(target)).toEqual(['bread', 'eggs', 'milk', 'apples']);
		expect([...list.tags].sort()).toEqual(['Bakery', 'Lidl', 'Market', 'lidl']);
		expect(list.hide_done.mode).toBe('off');
		expect(items.find((item) => item.name === 'milk')?.tags).toEqual(['Lidl', 'Market']);
	} finally {
		await unmount(component);
		for (const room of fixtureHandles) room.release();
		target.remove();
	}
});

it.each([
	['existing', 5],
	['new', 1]
] as const)('remounts from saved combined edit feed for %s item', async (name, initialSeq) => {
	const list = makeList({ tags: ['Shop'] });
	let saved = makeItem(list.uid, { name, changed_seq: initialSeq });
	const feed = () =>
		makeFeed({ full: true, seq: saved.changed_seq, lists: [list], items: [saved] });
	const fixture = await readyRoom(feed());
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		if (op.type === 'item.toggle_tag')
			saved = { ...saved, tags: ['Shop'], changed_seq: saved.changed_seq + 1 };
		else if (op.type === 'item.edit' && op.base_seq === saved.changed_seq)
			saved = {
				...saved,
				name: op.name,
				description: op.description,
				changed_seq: saved.changed_seq + 1
			};
		else
			return {
				op_id: op.op_id,
				status: 'rejected',
				code: 'changed_meanwhile',
				message: 'Stale edit',
				seq: saved.changed_seq
			};
		fixture.setFeed(feed());
		return applied(op, saved.changed_seq, { changed_seq: saved.changed_seq });
	});
	const target = document.createElement('div');
	document.body.append(target);
	let component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	let fresh: Awaited<ReturnType<typeof readyRoom>> | undefined;
	try {
		flushSync();
		(target.querySelector('button.name') as HTMLButtonElement).click();
		flushSync();
		fill(target.querySelector('textarea')!, 'Keep cold');
		click(target.querySelector('dialog')!, 'Shop');
		await waitFor(() =>
			expect(fixture.room.store.item(saved.uid)?.changed_seq).toBe(initialSeq + 1)
		);
		flushSync();
		expect(target.querySelector('textarea')!.value).toBe('Keep cold');
		submit(target.querySelector('dialog')!);
		await waitFor(() => expect(fixture.api.sendOp).toHaveBeenCalledTimes(2));
		expect(fixture.api.sendOp.mock.calls[1][1]).toMatchObject({
			type: 'item.edit',
			base_seq: initialSeq + 1,
			description: 'Keep cold',
			name
		});
		await waitFor(() => {
			flushSync();
			expect(target.querySelector('dialog')).toBeNull();
		});
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		expect(saved).toMatchObject({ description: 'Keep cold', tags: ['Shop'] });
		await unmount(component);
		fixture.room.release();
		fresh = await readyRoom(feed());
		component = mount(ListHarness, { target, props: { room: fresh.room, uid: list.uid } });
		flushSync();
		(target.querySelector('button.name') as HTMLButtonElement).click();
		flushSync();
		expect(target.querySelector('textarea')!.value).toBe('Keep cold');
		expect(target.querySelector('dialog button.chip')?.getAttribute('aria-pressed')).toBe('true');
		expect(fresh.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		fixture.room.release();
		fresh?.room.release();
		target.remove();
	}
});

it.each([
	['offline_quantity_button_queues_delta', 'quantity'],
	['offline_tag_click_sets_pressed_state', 'tag']
] as const)('%s', async (_name, kind) => {
	const list = makeList({ tags: ['Market'] });
	const milk = makeItem(list.uid);
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });

	try {
		await fixture.offline();
		flushSync();
		if (kind === 'quantity') {
			click(target, 'Options');
			const quantities = [...target.querySelectorAll('label')]
				.find((label) => label.textContent?.trim() === 'Show quantities')!
				.querySelector('input')!;
			if (!quantities.checked) quantities.click();
			flushSync();
			click(target, 'Done');
			click(target, 'More milk');
			expect(target.querySelector('[aria-label="Quantity of milk"]')?.textContent).toContain('2');
		} else {
			click(target, 'Market tag for milk');
			expect(
				target.querySelector('[aria-label="Market tag for milk"]')?.getAttribute('aria-pressed')
			).toBe('true');
		}
		await waitFor(async () => expect(await fixture.queue.read()).toHaveLength(1));
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
		expect(fixture.room.queuedOps[0]).toEqual(
			kind === 'quantity'
				? {
						op_id: expect.any(String),
						type: 'item.quantity_delta',
						list_uid: list.uid,
						item_uid: milk.uid,
						delta: 1
					}
				: {
						op_id: expect.any(String),
						type: 'item.toggle_tag',
						list_uid: list.uid,
						item_uid: milk.uid,
						tag: 'Market',
						active: true
					}
		);
		expect(target.querySelector('[data-item-uid] [aria-label="Not sent yet"]')).not.toBeNull();
		fixture.api.sendOp.mockImplementation(async (_slug, op) => applied(op, 2, { changed_seq: 2 }));
		fixture.setFeed(
			makeFeed({
				seq: 2,
				full: true,
				lists: [list],
				items: [
					{
						...milk,
						changed_seq: 2,
						...(kind === 'quantity' ? { quantity: 2 } : { tags: ['Market'] })
					}
				]
			})
		);
		fixture.online();
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
		expect(target.querySelector('[data-item-uid] [aria-label="Not sent yet"]')).toBeNull();
		expect(fixture.room.store.notSaved).toEqual([]);
		if (kind === 'quantity')
			expect(target.querySelector('[aria-label="Quantity of milk"]')?.textContent).toContain('2');
		else
			expect(
				target.querySelector('[aria-label="Market tag for milk"]')?.getAttribute('aria-pressed')
			).toBe('true');
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
		localStorage.clear();
	}
});

it('online typing preserves hidden checked rows', async () => {
	const list = makeList();
	const milk = makeItem(list.uid, { done: true, completed_at: '2026-11-02T12:00:00Z' });
	const bread = makeItem(list.uid, { name: 'bread' });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk, bread] }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		expect(op).toMatchObject({ type: 'list.visibility', mode: 'all', list_uid: list.uid });
		fixture.setFeed(
			makeFeed({
				full: true,
				seq: 2,
				lists: [{ ...list, changed_seq: 2, hide_done: { ...list.hide_done, mode: 'all' } }],
				items: [milk, bread]
			})
		);
		return applied(op, 2);
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		flushSync();
		click(target, 'Options');
		const hide = [...target.querySelectorAll('label')]
			.find((label) => label.textContent?.trim() === 'Hide checked-off items')!
			.querySelector('input')!;
		hide.click();
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
		expect(fixture.room.store.list(list.uid)?.hide_done.mode).toBe('all');
		expect(rowNames(target)).toEqual(['bread']);
		for (const text of ['mil', 'b', 'zzz']) {
			fill(target.querySelector('input[aria-label="Add or Search"]')!, text);
			expect(rowNames(target)).toEqual(['bread']);
			expect(fixture.room.store.unconfirmedView).toBe(false);
			expect(button(target, 'Add').disabled).toBe(false);
		}
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(1);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('hidden count copy follows store not search', async () => {
	let list = makeList();
	let items = [
		makeItem(list.uid, { done: true, completed_at: '2026-11-02T12:00:00Z' }),
		makeItem(list.uid, { name: 'eggs', done: true, completed_at: '2026-11-02T12:00:00Z' }),
		makeItem(list.uid, { name: 'bread' })
	];
	let seq = 1;
	const feed = () => makeFeed({ full: true, seq, lists: [list], items });
	const fixture = await readyRoom(feed());
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		seq += 1;
		if (op.type === 'list.visibility') {
			list = { ...list, changed_seq: seq, hide_done: { ...list.hide_done, mode: op.mode! } };
		} else {
			expect(op).toMatchObject({ type: 'item.add', name: 'milk', list_uid: list.uid });
			items = items.map((item) =>
				item.name === 'milk' ? { ...item, done: false, completed_at: null, changed_seq: seq } : item
			);
		}
		fixture.setFeed(feed());
		return applied(op, seq, { outcome: 'restored', item_uid: items[0].uid });
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const line = () => target.querySelector('.hidden-count')?.textContent;
	const settled = async () => {
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
	};
	try {
		flushSync();
		expect(line()).toBeUndefined();
		click(target, 'Options');
		const hide = [...target.querySelectorAll('label')]
			.find((label) => label.textContent?.trim() === 'Hide checked-off items')!
			.querySelector('input')!;
		hide.click();
		await settled();
		expect(line()).toBe('2 checked items hidden');
		const input = target.querySelector<HTMLInputElement>('input[aria-label="Add or Search"]')!;
		input.focus();
		fill(input, 'milk');
		expect(line()).toBe('2 checked items hidden');
		const suggestion = [...target.querySelectorAll<HTMLElement>('[role="option"]')].find(
			(option) => option.querySelector('span')?.textContent === 'milk'
		)!;
		expect(suggestion).toBeDefined();
		suggestion.click();
		await settled();
		expect(fixture.room.store.item(items[0].uid)?.done).toBe(false);
		expect(line()).toBe('1 checked item hidden');
		// A peer checks milk again: take the update through the real live feed.
		seq += 1;
		items = items.map((item) =>
			item.name === 'milk'
				? { ...item, done: true, completed_at: '2026-11-02T12:00:00Z', changed_seq: seq }
				: item
		);
		fixture.setFeed(feed());
		fixture.stream().seq(seq);
		await waitFor(() => expect(fixture.room.store.seq).toBe(seq));
		flushSync();
		expect(line()).toBe('2 checked items hidden');
		hide.click();
		await settled();
		expect(list.hide_done.mode).toBe('off');
		expect(line()).toBeUndefined();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('typing during revalidation keeps confirmed rows', async () => {
	const list = makeList();
	const items = ['bread', 'milk'].map((name) => makeItem(list.uid, { name }));
	const connectivity = new EventTarget();
	const snapshots = createSnapshotStore({ indexedDB: new IDBFactory(), channel: null });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items }), {
		online: connectivity,
		snapshotStore: snapshots
	});
	await waitFor(() => expect(fixture.room.store.savedAt).toBeTruthy());
	const answer = deferred<typeof ROOM>();
	fixture.api.whoAmI.mockImplementation(() => answer.promise);
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const notice = mount(SavedViewNotice, { target, props: { room: fixture.room } });
	try {
		flushSync();
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		const calls = fixture.api.whoAmI.mock.calls.length;
		connectivity.dispatchEvent(Object.assign(new Event('pageshow'), { persisted: true }));
		await waitFor(() => expect(fixture.api.whoAmI).toHaveBeenCalledTimes(calls + 1));
		expect(fixture.room.store.canWrite).toBe(false);
		expect(fixture.room.store.canEdit).toBe(true);
		fill(target.querySelector('input[aria-label="Add or Search"]')!, 'zzz');
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		expect(button(target, 'Add').disabled).toBe(false);
		expect(target.querySelector('.saved-notice')).toBeNull();
		expect(fixture.room.store.showsOfflineNotice).toBe(false);
		expect(fixture.room.store.unconfirmedView).toBe(false);
		answer.resolve(ROOM);
		await waitFor(() => expect(fixture.room.store.canWrite).toBe(true));
		flushSync();
		expect(rowNames(target)).toEqual(['bread', 'milk']);
	} finally {
		answer.resolve(ROOM);
		await unmount(notice);
		await unmount(component);
		fixture.room.release();
		snapshots.close();
		target.remove();
	}
});

it('offline_unsent_mark_tracks_only_pending_row', async () => {
	const list = makeList();
	const milk = makeItem(list.uid);
	const bread = makeItem(list.uid, { name: 'bread' });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk, bread] }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const mark = (uid: string) =>
		target.querySelector(`[data-item-uid="${uid}"] [aria-label="Not sent yet"]`);
	try {
		await fixture.offline();
		flushSync();
		expect(mark(milk.uid)).toBeNull();
		expect(mark(bread.uid)).toBeNull();
		(target.querySelector('input[aria-label="milk"]') as HTMLInputElement).click();
		await waitFor(async () => expect(await fixture.queue.read()).toHaveLength(1));
		flushSync();
		expect(mark(milk.uid)).not.toBeNull();
		expect(mark(bread.uid)).toBeNull();
		expect(target.querySelectorAll('[aria-label="Not sent yet"]')).toHaveLength(1);
		expect((target.querySelector('input[aria-label="milk"]') as HTMLInputElement).checked).toBe(
			true
		);
		expect((target.querySelector('input[aria-label="bread"]') as HTMLInputElement).checked).toBe(
			false
		);
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
		fixture.api.sendOp.mockImplementation(async (_slug, op) => applied(op, 2, { changed_seq: 2 }));
		fixture.setFeed(
			makeFeed({
				seq: 2,
				full: true,
				lists: [list],
				items: [
					{ ...milk, done: true, completed_at: '2026-11-02T12:00:00Z', changed_seq: 2 },
					bread
				]
			})
		);
		fixture.online();
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
		expect(target.querySelectorAll('[aria-label="Not sent yet"]')).toHaveLength(0);
		expect((target.querySelector('input[aria-label="milk"]') as HTMLInputElement).checked).toBe(
			true
		);
		expect((target.querySelector('input[aria-label="bread"]') as HTMLInputElement).checked).toBe(
			false
		);
		expect(fixture.room.store.notSaved).toEqual([]);
		expect(await fixture.queue.read()).toEqual([]);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it.each([false, true])(
	'public share omits room menu and personal reminder text with settings enabled: %s',
	async (enabled) => {
		reminderSettings.enabled = enabled;
		const list = makeList({ slug: '' });
		const guest = await readyShare(
			makeFeed({ full: true, room: null, lists: [list], items: [makeItem(list.uid)] })
		);
		const target = document.createElement('div');
		document.body.append(target);
		const component = mount(ListView, {
			target,
			props: { room: guest.room, list, roomHref: null, canReset: false }
		});
		try {
			flushSync();
			expect(target.querySelector('h1')?.textContent).toBe('Groceries');
			expect(target.querySelector('[aria-label="List menu"]')).not.toBeNull();
			click(target, 'Options');
			expect(target.querySelector('[aria-label="Room menu"]')).toBeNull();
			expect(target.textContent).not.toContain('Personal list reminders');
			expect(target.textContent).not.toContain('Personal reminders');
			click(target, 'Due items: none due');
			expect(target.querySelector('dialog')).not.toBeNull();
			expect(target.querySelector('dialog')?.textContent).not.toMatch(
				/reminder policy|Reminder settings/
			);
			expect(guest.room.store.room).toBeNull();
		} finally {
			await unmount(component);
			guest.room.release();
			target.remove();
		}
	}
);

it('extends hold until HOLD_MS after the last checkbox tap', async () => {
	const list = makeList();
	const items = ['apple', 'milk', 'zucchini'].map((name) => makeItem(list.uid, { name }));
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items }), {
		queueStorage: new MemoryQueueStorage()
	});
	await fixture.offline();
	const setDone = vi.spyOn(fixture.room, 'setDone');
	const target = document.createElement('div');
	document.body.append(target);
	vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const tick = async (name: string) => {
		(target.querySelector(`input[aria-label="${name}"]`) as HTMLInputElement).click();
		await setDone.mock.results.at(-1)!.value;
		flushSync();
		expect((target.querySelector(`input[aria-label="${name}"]`) as HTMLInputElement).checked).toBe(
			true
		);
	};
	try {
		flushSync();
		expect(rowNames(target)).toEqual(['apple', 'milk', 'zucchini']);
		await tick('apple');
		expect(fixture.room.store.item(items[0].uid)?.done).toBe(true);
		expect(rowNames(target)).toEqual(['apple', 'milk', 'zucchini']);
		const gap = Math.floor(HOLD_MS / 2);
		await vi.advanceTimersByTimeAsync(gap);
		await tick('milk');
		expect(fixture.room.store.item(items[1].uid)?.done).toBe(true);
		expect(rowNames(target)).toEqual(['apple', 'milk', 'zucchini']);
		await vi.advanceTimersByTimeAsync(HOLD_MS - gap + 1);
		flushSync();
		// Past the first deadline, but still inside the second hold.
		expect(rowNames(target)).toEqual(['apple', 'milk', 'zucchini']);
		await vi.advanceTimersByTimeAsync(gap - 2);
		flushSync();
		expect(rowNames(target)).toEqual(['apple', 'milk', 'zucchini']);
		await vi.advanceTimersByTimeAsync(1);
		flushSync();
		expect(rowNames(target)).toEqual(['zucchini', 'apple', 'milk']);
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		fixture.room.release();
		setDone.mockRestore();
		vi.useRealTimers();
		target.remove();
	}
});

it('removing a selected tag from a live feed restores all rows', async () => {
	const list = makeList({ tags: ['Lidl'] });
	const milk = makeItem(list.uid, { name: 'milk', tags: ['Lidl'] });
	const bread = makeItem(list.uid, { name: 'bread' });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk, bread] }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		flushSync();
		click(target.querySelector('ul.chips')!, 'Lidl');
		expect(rowNames(target)).toEqual(['milk']);
		fixture.setFeed(makeFeed({ seq: 2, lists: [{ ...list, tags: [], changed_seq: 2 }] }));
		fixture.stream().seq(2);
		await waitFor(() => {
			flushSync();
			expect(target.querySelector('ul.chips')).toBeNull();
		});
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		expect(fixture.room.store.item(milk.uid)?.tags).toEqual(['Lidl']);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it.each([
	['existing item', 5, true, true],
	['newly created item', 1, true, true],
	['description only', 5, true, false],
	['tag only', 5, false, true]
] as const)('saves and reopens %s', async (_label, initialSeq, editDescription, editTag) => {
	const list = makeList({ tags: ['Shop'] });
	let saved = makeItem(list.uid, { name: 'milk', changed_seq: initialSeq });
	const store = createRoomStore(ROOM.slug, {
		changes: vi.fn(async () =>
			makeFeed({ seq: saved.changed_seq, full: true, lists: [list], items: [saved] })
		)
	});
	await store.refresh();
	const editItem = vi.fn(async (base: Item, changes: Partial<Item>) => {
		if (base.changed_seq !== saved.changed_seq) return { ok: false, code: 'conflict' };
		saved = { ...saved, ...changes, changed_seq: saved.changed_seq + 1 };
		await store.refresh();
		return { ok: true };
	});
	const toggleItemTag = vi.fn(async () => {
		saved = { ...saved, tags: ['Shop'], changed_seq: saved.changed_seq + 1 };
		await store.refresh();
		return { ok: true };
	});
	const room = {
		slug: ROOM.slug,
		store,
		editItem,
		toggleItemTag,
		queuedOps: []
	} as unknown as RoomHandle;
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListView, {
		target,
		props: { room, list, roomHref: null, canReset: false }
	});
	try {
		flushSync();
		(target.querySelector('button.name') as HTMLButtonElement).click();
		flushSync();
		const notes = target.querySelector('textarea')!;
		if (editDescription) {
			notes.value = 'Keep cold';
			notes.dispatchEvent(new Event('input', { bubbles: true }));
		}
		if (editTag) {
			(target.querySelector('dialog button.chip') as HTMLButtonElement).click();
			await waitFor(() => expect(store.item(saved.uid)?.tags).toEqual(['Shop']));
			flushSync();
			// Tags save immediately, but must not clear the unsaved notes.
			expect(notes.value).toBe(editDescription ? 'Keep cold' : '');
		}
		const save = target.querySelector('dialog button[type="submit"]') as HTMLButtonElement;
		expect(save.disabled).toBe(false);
		target
			.querySelector('dialog form')!
			.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
		await waitFor(() => expect(editItem).toHaveBeenCalledTimes(1));
		expect(editItem.mock.calls[0][0].changed_seq).toBe(initialSeq + (editTag ? 1 : 0));
		await waitFor(() => {
			flushSync();
			expect(target.querySelector('textarea')).toBeNull();
		});
		expect(editItem).toHaveBeenCalledTimes(1);
		expect(saved.description).toBe(editDescription ? 'Keep cold' : '');
		expect(saved.tags).toEqual(editTag ? ['Shop'] : []);
		(target.querySelector('button.name') as HTMLButtonElement).click();
		flushSync();
		expect(target.querySelector('textarea')!.value).toBe(saved.description);
		expect(target.querySelector('dialog button.chip')?.getAttribute('aria-pressed')).toBe(
			String(editTag)
		);
	} finally {
		await unmount(component);
		target.remove();
	}
});

it('startup with loaded due data does not emit a due toast', async () => {
	const previousNow = dueClock.now;
	vi.setSystemTime(new Date('2026-11-02T12:00:00Z'));
	advanceDueClock(new Date());
	const list = makeList();
	const feed = makeFeed({
		full: true,
		lists: [list],
		items: [makeItem(list.uid, { date: '2026-11-02' })]
	});
	const fixture = await readyRoom(feed);
	const show = vi.spyOn(toasts, 'show');
	const target = document.createElement('div');
	document.body.append(target);
	let component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		flushSync();
		await tick();
		expect(button(target, 'Due items: 1 due, 0 overdue')).toBeDefined();
		await fixture.refresh({ ...feed, seq: 2 });
		flushSync();
		await tick();
		await unmount(component);
		component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
		flushSync();
		await tick();
		expect(button(target, 'Due items: 1 due, 0 overdue')).toBeDefined();
		expect(show).not.toHaveBeenCalled();
		expect(toasts.items).toEqual([]);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
		show.mockRestore();
		vi.useRealTimers();
		advanceDueClock(previousNow);
	}
});

it('missing reveal UID shows no-longer-on-list status', async () => {
	const list = makeList();
	const milk = makeItem(list.uid);
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		flushSync();
		expect(target.querySelector('[role="status"]')).toBeNull();
		Object.assign(page, { url: new URL('http://localhost/list/test?item=no-such-item&at=1') });
		flushSync();
		expect(target.querySelector('[role="status"]')?.textContent?.trim()).toBe(
			'That item is no longer on this list. Its date may have changed, or it was deleted.'
		);
		expect(rowNames(target)).toEqual(['milk']);
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('failed saved-view revalidation keeps notice and Add enabled', async () => {
	const list = makeList();
	const items = ['bread', 'milk'].map((name) => makeItem(list.uid, { name }));
	const snapshots = createSnapshotStore({ indexedDB: new IDBFactory(), channel: null });
	const connectivity = new EventTarget();
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items }), {
		snapshotStore: snapshots,
		online: connectivity
	});
	await waitFor(() => expect(fixture.room.store.savedAt).toBeTruthy());
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const notice = mount(SavedViewNotice, { target, props: { room: fixture.room } });
	try {
		for (const failure of [new NetworkError(), new ApiError(503, 'unavailable', 'Try later.')]) {
			const calls = fixture.api.whoAmI.mock.calls.length;
			fixture.api.whoAmI.mockRejectedValue(failure);
			connectivity.dispatchEvent(new Event('online'));
			await waitFor(() => expect(fixture.api.whoAmI).toHaveBeenCalledTimes(calls + 1));
			await waitFor(() => expect(fixture.room.store.error).toBe(failure.message));
			flushSync();
			expect(rowNames(target)).toEqual(['bread', 'milk']);
			expect(target.querySelector('.saved-notice')?.textContent).toBe(
				'Offline — changes are saved on this phone.'
			);
			expect(button(target, 'Add').disabled).toBe(false);
			expect(fixture.room.store.canWrite).toBe(false);
			expect(fixture.api.sendOp).not.toHaveBeenCalled();
		}
		fixture.api.whoAmI.mockResolvedValue(ROOM);
		connectivity.dispatchEvent(new Event('online'));
		await waitFor(() => expect(fixture.room.store.canWrite).toBe(true));
		flushSync();
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		expect(target.querySelector('.saved-notice')).toBeNull();
		expect(button(target, 'Add').disabled).toBe(false);
	} finally {
		await unmount(notice);
		await unmount(component);
		fixture.room.release();
		snapshots.close();
		target.remove();
	}
});

it('loads shared show_on_items false into rows and Tags switch from a fresh full feed', async () => {
	let list = makeList({ tags: ['Lidl'] });
	const milk = makeItem(list.uid, { tags: ['Lidl'] });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		expect(op).toMatchObject({
			type: 'list.tag_settings',
			list_uid: list.uid,
			show_on_items: false
		});
		list = {
			...list,
			changed_seq: 2,
			tag_settings: { ...list.tag_settings, show_on_items: false }
		};
		fixture.setFeed(makeFeed({ seq: 2, full: true, lists: [list], items: [milk] }));
		return applied(op, 2);
	});
	const target = document.createElement('div');
	document.body.append(target);
	let component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	let fresh: Awaited<ReturnType<typeof readyRoom>> | undefined;
	const showTags = () =>
		[...target.querySelectorAll('label')]
			.find((label) => label.textContent?.trim() === 'Show tags on items')!
			.querySelector('input')!;
	try {
		flushSync();
		expect(button(target, 'Lidl tag for milk')).toBeDefined();
		click(target, 'Options');
		click(target, 'Tags');
		expect(showTags().checked).toBe(true);
		showTags().click();
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
		expect(showTags().checked).toBe(false);
		click(target.querySelector('dialog')!, 'Close');
		expect(target.querySelector('[aria-label="Lidl tag for milk"]')).toBeNull();
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(1);
		await unmount(component);
		fixture.room.release();
		fresh = await readyRoom(makeFeed({ seq: 2, full: true, lists: [list], items: [milk] }));
		component = mount(ListHarness, { target, props: { room: fresh.room, uid: list.uid } });
		flushSync();
		expect(target.querySelector('[aria-label="Lidl tag for milk"]')).toBeNull();
		click(target, 'Options');
		click(target, 'Tags');
		expect(showTags().checked).toBe(false);
		expect(fresh.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		fixture.room.release();
		fresh?.room.release();
		target.remove();
	}
});

it('dialog count refreshes on check and uncheck and stays off rows', async () => {
	const list = makeList();
	let milk = makeItem(list.uid, { added_at: '2026-11-02T12:34:00Z' });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	let seq = 1;
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		expect(op.type).toBe('item.set_done');
		if (op.type !== 'item.set_done') throw new Error(`Unexpected ${op.type}`);
		seq += 1;
		milk = {
			...milk,
			changed_seq: seq,
			done: op.done,
			completed_at: op.done ? '2026-11-02T13:00:00Z' : null,
			add_count: op.done ? 1 : 2,
			added_at: op.done ? milk.added_at : '2026-11-02T14:56:00Z'
		};
		fixture.setFeed(makeFeed({ seq, full: true, lists: [list], items: [milk] }));
		return applied(op, seq, { changed_seq: seq });
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const open = () => {
		(target.querySelector('button.name') as HTMLButtonElement).click();
		flushSync();
	};
	try {
		flushSync();
		for (const [step, count] of [
			[0, 'Added once'],
			[1, 'Added once'],
			[2, 'Added 2 times']
		] as const) {
			if (step > 0) {
				(target.querySelector('input[aria-label="milk"]') as HTMLInputElement).click();
				await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
				flushSync();
			}
			open();
			expect(target.querySelector('dialog')?.textContent).toContain(count);
			expect(target.querySelector('dialog')?.textContent).toMatch(
				/Last added \d{4}-\d{2}-\d{2} \d{2}:\d{2}/
			);
			click(target.querySelector('dialog')!, 'Cancel');
			expect(target.querySelector('dialog')).toBeNull();
			expect(target.querySelector('ul.items')?.textContent).not.toMatch(
				/Added once|Added \d+ times|Last added/
			);
		}
		expect(fixture.api.sendOp.mock.calls.map(([, op]) => op)).toEqual([
			expect.objectContaining({ type: 'item.set_done', item_uid: milk.uid, done: true }),
			expect.objectContaining({ type: 'item.set_done', item_uid: milk.uid, done: false })
		]);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('single-tag confirmation cancels or keeps first tags through TagsDialog and parent updates', async () => {
	let list = makeList({ tags: ['Lidl', 'Market'] });
	let milk = makeItem(list.uid, { tags: ['Lidl', 'Market'] });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		expect(op).toMatchObject({ type: 'list.tag_settings', list_uid: list.uid, mode: 'single' });
		list = { ...list, changed_seq: 2, tag_settings: { ...list.tag_settings, mode: 'single' } };
		milk = { ...milk, changed_seq: 2, tags: ['Lidl'] };
		fixture.setFeed(makeFeed({ seq: 2, full: true, lists: [list], items: [milk] }));
		return applied(op, 2);
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const confirm = () =>
		[...target.querySelectorAll('dialog')].find((dialog) =>
			dialog.textContent?.includes('Keep first tags')
		)!;
	try {
		flushSync();
		click(target, 'Options');
		click(target, 'Tags');
		click(target, 'One tag per item');
		expect(confirm().querySelector('h2')?.textContent).toContain('1 item has several tags');
		click(confirm(), 'Cancel');
		expect(target.querySelectorAll('dialog')).toHaveLength(1);
		expect(button(target, 'One tag per item').getAttribute('aria-pressed')).toBe('false');
		expect(fixture.room.store.item(milk.uid)?.tags).toEqual(['Lidl', 'Market']);
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
		click(target, 'One tag per item');
		click(confirm(), 'Keep first tags');
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
		expect(target.querySelectorAll('dialog')).toHaveLength(1);
		expect(button(target, 'One tag per item').getAttribute('aria-pressed')).toBe('true');
		click(target.querySelector('dialog')!, 'Close');
		expect(button(target, 'Lidl tag for milk').getAttribute('aria-pressed')).toBe('true');
		expect(button(target, 'Market tag for milk').getAttribute('aria-pressed')).toBe('false');
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(1);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('renders Color 7 then deletes and undoes a tag', async () => {
	let list = makeList({ tags: ['Lidl'] });
	const milk = makeItem(list.uid, { tags: ['Lidl'] });
	let seq = 1;
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		seq += 1;
		if (op.type === 'list.tag_color') {
			expect(op).toMatchObject({ tag: 'Lidl', color: 6 });
			list = { ...list, tag_settings: { ...list.tag_settings, colors: { Lidl: 6 } } };
		} else if (op.type === 'list.tag_remove') {
			expect(op.tag).toBe('Lidl');
			list = { ...list, tags: [] };
		} else if (op.type === 'list.tag_add') {
			expect(op.tag).toBe('Lidl');
			list = { ...list, tags: ['Lidl'] };
		} else if (op.type === 'list.tag_rename') {
			expect(op).toMatchObject({ tag: 'Lidl', new_tag: 'Lidl' });
		} else throw new Error(`Unexpected ${op.type}`);
		list = { ...list, changed_seq: seq };
		fixture.setFeed(makeFeed({ seq, full: true, lists: [list], items: [milk] }));
		return applied(op, seq);
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const settled = async () => {
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
	};
	const tagCard = () => click(target.querySelector('ul.chips')!, 'Lidl');
	try {
		flushSync();
		click(target, 'Options');
		tagCard();
		click(target.querySelector('dialog')!, 'Color 7');
		await settled();
		submit(target.querySelector('dialog')!);
		await waitFor(() => {
			flushSync();
			expect(target.querySelector('dialog')).toBeNull();
		});
		click(target, 'Done');
		expect(button(target, 'Lidl tag for milk').style.getPropertyValue('--tag')).toBe(
			'var(--tag-6)'
		);
		click(target, 'Options');
		tagCard();
		click(target.querySelector('dialog')!, 'Delete tag');
		await settled();
		expect(target.querySelector('dialog')).toBeNull();
		expect(target.textContent).toContain('Deleted tag Lidl');
		expect(target.querySelector('[aria-label="Lidl tag for milk"]')).toBeNull();
		click(target, 'Undo');
		await settled();
		expect(target.textContent).toContain('Restored tag Lidl');
		expect(button(target, 'Lidl tag for milk').getAttribute('aria-pressed')).toBe('true');
		expect(fixture.api.sendOp.mock.calls.map(([, op]) => op.type)).toEqual([
			'list.tag_color',
			'list.tag_rename',
			'list.tag_remove',
			'list.tag_add'
		]);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('keeps immediate tag toggles after Cancel', async () => {
	const list = makeList({ tags: ['Lidl', 'Market'] });
	let milk = makeItem(list.uid);
	let seq = 1;
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	const firstAnswer = deferred<void>();
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		expect(op.type).toBe('item.toggle_tag');
		if (op.type !== 'item.toggle_tag') throw new Error(`Unexpected ${op.type}`);
		if (seq === 1) await firstAnswer.promise;
		seq += 1;
		milk = {
			...milk,
			changed_seq: seq,
			tags: op.active ? [...milk.tags, op.tag] : milk.tags.filter((tag) => tag !== op.tag)
		};
		fixture.setFeed(makeFeed({ seq, full: true, lists: [list], items: [milk] }));
		return applied(op, seq, { changed_seq: seq });
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		flushSync();
		(target.querySelector('button.name') as HTMLButtonElement).click();
		flushSync();
		for (const [index, tag, lidl, market] of [
			[0, 'Lidl', true, false],
			[1, 'Market', true, true],
			[2, 'Lidl', false, true]
		] as const) {
			click(target.querySelector('dialog')!, tag);
			// The real queue projects synchronously, before the held network answer.
			expect(button(target.querySelector('dialog')!, tag).getAttribute('aria-pressed')).toBe(
				String(tag === 'Lidl' ? lidl : market)
			);
			expect(button(target.querySelector('dialog')!, 'Lidl').getAttribute('aria-pressed')).toBe(
				String(lidl)
			);
			expect(button(target.querySelector('dialog')!, 'Market').getAttribute('aria-pressed')).toBe(
				String(market)
			);
			if (index === 0) {
				await waitFor(() => expect(fixture.api.sendOp).toHaveBeenCalledTimes(1));
				expect(fixture.room.store.pendingOps).toHaveLength(1);
				firstAnswer.resolve();
			}
			await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
			flushSync();
		}
		click(target.querySelector('dialog')!, 'Cancel');
		expect(target.querySelector('dialog')).toBeNull();
		expect(button(target, 'Lidl tag for milk').getAttribute('aria-pressed')).toBe('false');
		expect(button(target, 'Market tag for milk').getAttribute('aria-pressed')).toBe('true');
		expect(fixture.api.sendOp.mock.calls.map(([, op]) => op)).toEqual([
			expect.objectContaining({ type: 'item.toggle_tag', tag: 'Lidl', active: true }),
			expect.objectContaining({ type: 'item.toggle_tag', tag: 'Market', active: true }),
			expect.objectContaining({ type: 'item.toggle_tag', tag: 'Lidl', active: false })
		]);
	} finally {
		firstAnswer.resolve();
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('renamed tag stays selected in the parent filter', async () => {
	let list = makeList({ tags: ['Lidl'] });
	let milk = makeItem(list.uid, { tags: ['Lidl'] });
	const bread = makeItem(list.uid, { name: 'bread' });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk, bread] }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		expect(op).toMatchObject({
			type: 'list.tag_rename',
			list_uid: list.uid,
			tag: 'Lidl',
			new_tag: 'Aldi'
		});
		list = { ...list, tags: ['Aldi'], changed_seq: 2 };
		milk = { ...milk, tags: ['Aldi'], changed_seq: 2 };
		fixture.setFeed(makeFeed({ seq: 2, full: true, lists: [list], items: [milk, bread] }));
		return applied(op, 2);
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const chips = () => target.querySelector('ul.chips')!;
	try {
		flushSync();
		click(chips(), 'Lidl');
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('true');
		expect(rowNames(target)).toEqual(['milk']);
		expect(target.querySelector('dialog')).toBeNull();
		click(target, 'Options');
		click(chips(), 'Lidl');
		expect(target.querySelector('dialog h2')?.textContent).toBe('Edit Tag');
		expect(rowNames(target)).toEqual(['milk']);
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('true');
		fill(target.querySelector('dialog input')!, 'Aldi');
		submit(target.querySelector('dialog')!);
		await waitFor(() => {
			flushSync();
			expect(target.querySelector('dialog')).toBeNull();
		});
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		click(target, 'Done');
		expect(button(chips(), 'Aldi').getAttribute('aria-pressed')).toBe('true');
		expect(chips().textContent).not.toContain('Lidl');
		expect(button(target, 'Aldi tag for milk').getAttribute('aria-pressed')).toBe('true');
		expect(target.querySelector('[aria-label="Lidl tag for milk"]')).toBeNull();
		expect(rowNames(target)).toEqual(['milk']);
		click(chips(), 'Aldi');
		expect(button(chips(), 'Aldi').getAttribute('aria-pressed')).toBe('false');
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(1);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('empty hint and Clear follow parent filter state with empty feed and adds', async () => {
	const list = makeList({ tags: ['Lidl'] });
	const items: Item[] = [];
	let seq = 1;
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		if (op.type !== 'item.add') throw new Error(`Unexpected ${op.type}`);
		expect(['milk', 'apple']).toContain(op.name);
		expect(op.list_uid).toBe(list.uid);
		seq += 1;
		const item = makeItem(list.uid, {
			name: op.name,
			tags: op.name === 'milk' ? ['Lidl'] : [],
			changed_seq: seq
		});
		items.push(item);
		fixture.setFeed(makeFeed({ seq, full: true, lists: [list], items: [...items] }));
		return applied(op, seq, { outcome: 'added', item_uid: item.uid, changed_seq: seq });
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const chips = () => target.querySelector('ul.chips')!;
	try {
		flushSync();
		expect(target.querySelector('.empty')?.textContent).toBe('No items yet. Type below to add.');
		expect(chips().querySelector('button.clear')).toBeNull();
		for (const name of ['milk', 'apple']) {
			fill(target.querySelector('input[aria-label="Add or Search"]')!, name);
			submit(target.querySelector('.add')!);
			await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
			flushSync();
			expect(target.querySelector('.empty')).toBeNull();
		}
		expect(rowNames(target)).toEqual(['apple', 'milk']);
		expect(chips().querySelector('button.clear')).toBeNull();
		click(chips(), 'Lidl');
		expect(rowNames(target)).toEqual(['milk']);
		expect(button(chips(), 'Clear')).toBeDefined();
		click(chips(), 'Clear');
		expect(chips().querySelector('button.clear')).toBeNull();
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('false');
		expect(rowNames(target)).toEqual(['apple', 'milk']);
		expect(target.querySelector('.empty')).toBeNull();
		expect(fixture.api.sendOp.mock.calls.map(([, op]) => op)).toEqual([
			expect.objectContaining({ type: 'item.add', name: 'milk' }),
			expect.objectContaining({ type: 'item.add', name: 'apple' })
		]);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('keeps Da Dr and inline tag color after adding Aisle', async () => {
	const list = makeList({ tags: ['Dairy', 'Dry goods'] });
	const milk = makeItem(list.uid);
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const dairy = () => button(target, 'Dairy tag for milk');
	try {
		flushSync();
		expect(dairy().textContent?.trim()).toBe('Da');
		expect(button(target, 'Dry goods tag for milk').textContent?.trim()).toBe('Dr');
		const color = dairy().style.getPropertyValue('--tag');
		expect(color).toMatch(/^var\(--tag-[0-6]\)$/);
		await fixture.refresh(
			makeFeed({
				seq: 2,
				full: true,
				lists: [{ ...list, changed_seq: 2, tags: ['Aisle', ...list.tags] }],
				items: [milk]
			})
		);
		flushSync();
		expect(button(target, 'Aisle tag for milk')).toBeDefined();
		expect(dairy().textContent?.trim()).toBe('Da');
		expect(button(target, 'Dry goods tag for milk').textContent?.trim()).toBe('Dr');
		expect(dairy().style.getPropertyValue('--tag')).toBe(color);
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('tag chip toggles filter and rows', async () => {
	const list = makeList({ tags: ['Lidl'] });
	const fixture = await readyRoom(
		makeFeed({
			full: true,
			lists: [list],
			items: [makeItem(list.uid, { tags: ['Lidl'] }), makeItem(list.uid, { name: 'bread' })]
		})
	);
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	const chips = () => target.querySelector('ul.chips')!;
	try {
		flushSync();
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('false');
		click(chips(), 'Lidl');
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('true');
		expect(rowNames(target)).toEqual(['milk']);
		click(chips(), 'Lidl');
		expect(button(chips(), 'Lidl').getAttribute('aria-pressed')).toBe('false');
		expect(rowNames(target)).toEqual(['bread', 'milk']);
		expect(target.querySelector('dialog')).toBeNull();
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('creates tags only through Options Tags', async () => {
	let list = makeList();
	const milk = makeItem(list.uid);
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		expect(op).toMatchObject({ type: 'list.tag_add', list_uid: list.uid, tag: 'Lidl' });
		list = { ...list, tags: ['Lidl'], changed_seq: 2 };
		fixture.setFeed(makeFeed({ seq: 2, full: true, lists: [list], items: [milk] }));
		return applied(op, 2);
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		flushSync();
		expect(target.querySelector('ul[aria-label="Tags"]')).toBeNull();
		expect(
			[...target.querySelectorAll('button')].map((node) => node.textContent?.trim())
		).not.toContain('New tag');
		expect(target.querySelector('input[aria-label="Add tag"]')).toBeNull();
		click(target, 'Options');
		expect(target.querySelector('input[aria-label="Add tag"]')).toBeNull();
		click(target, 'Tags');
		expect(target.querySelector('dialog input[aria-label="Add tag"]')).not.toBeNull();
		fill(target.querySelector('dialog input[aria-label="Add tag"]')!, 'Lidl');
		submit(target.querySelector('dialog')!);
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		flushSync();
		click(target.querySelector('dialog')!, 'Close');
		expect(target.querySelector('dialog')).toBeNull();
		expect(target.querySelectorAll('ul[aria-label="Tags"] button')).toHaveLength(1);
		expect(button(target.querySelector('ul.chips')!, 'Lidl')).toBeDefined();
		expect(target.querySelectorAll('[aria-label="Lidl tag for milk"]')).toHaveLength(1);
		expect(button(target, 'Lidl tag for milk').getAttribute('aria-pressed')).toBe('false');
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(1);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('shows queued Unicode feedback then removes rejected optimistic row', async () => {
	const list = makeList();
	const existing = makeItem(list.uid, { name: '\u1c89' });
	const initial = makeFeed({ full: true, lists: [list], items: [existing] });
	const fixture = await readyRoom(initial);
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		await fixture.offline();
		fixture.api.sendOp.mockClear();
		flushSync();
		const input = target.querySelector<HTMLInputElement>('input[aria-label="Add or Search"]')!;
		fill(input, '\u1c8a');
		submit(target.querySelector('.add')!);
		await waitFor(() => expect(toasts.items).toHaveLength(1));
		flushSync();
		expect(toasts.items.map((toast) => toast.message)).toEqual([
			'Queued; the server will check this item when online.'
		]);
		expect(toasts.items.some((toast) => toast.message.startsWith('Added '))).toBe(false);
		expect(input.value).toBe('');
		const clientSeesDuplicate = '\u1c89'.toLowerCase() === '\u1c8a'.toLowerCase();
		expect(rowNames(target)).toEqual(clientSeesDuplicate ? ['\u1c89'] : ['\u1c89', '\u1c8a']);
		await waitFor(async () => expect(await fixture.queue.read()).toHaveLength(1));
		const [stored] = await fixture.queue.read();
		expect(stored.op).toMatchObject({ type: 'item.add', list_uid: list.uid, name: '\u1c8a' });
		expect(fixture.api.sendOp).not.toHaveBeenCalled();
		fixture.api.sendOp.mockImplementation(async (_slug, op) => ({
			op_id: op.op_id,
			status: 'rejected',
			code: 'duplicate_active',
			message: 'The server considers this a duplicate.',
			seq: 1,
			item_uid: existing.uid
		}));
		fixture.setFeed(initial);
		fixture.online();
		await waitFor(async () => expect(await fixture.queue.read()).toEqual([]));
		flushSync();
		expect(fixture.room.store.pendingOps).toEqual([]);
		expect(rowNames(target)).toEqual(['\u1c89']);
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(1);
		expect(fixture.api.sendOp.mock.calls[0][1]).toEqual(stored.op);
		expect(toasts.items.some((toast) => toast.message.startsWith('Added '))).toBe(false);
		expect(fixture.room.store.notSaved).toEqual([]);
		expect(await fixture.queue.read()).toEqual([]);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('submits U+0085-trimmed names and renders normalized feedback', async () => {
	const list = makeList();
	const saved = makeItem(list.uid, { name: 'Oat Milk', changed_seq: 2 });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list] }));
	fixture.api.sendOp.mockImplementation(async (_slug, op) => {
		fixture.setFeed(makeFeed({ seq: 2, full: true, lists: [list], items: [saved] }));
		return applied(op, 2, { outcome: 'added', item_uid: saved.uid, changed_seq: 2 });
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListHarness, { target, props: { room: fixture.room, uid: list.uid } });
	try {
		flushSync();
		const input = target.querySelector<HTMLInputElement>('input[aria-label="Add or Search"]')!;
		fill(input, '\u0085Oat Milk\u0085');
		submit(target.querySelector('.add')!);
		await waitFor(() => expect(fixture.room.store.pendingOps).toEqual([]));
		await waitFor(() => expect(toasts.items).toHaveLength(1));
		flushSync();
		expect(toasts.items.map((toast) => toast.message)).toEqual(['Added Oat Milk']);
		expect(rowNames(target)).toEqual(['Oat Milk']);
		expect(input.value).toBe('');
		expect(fixture.api.sendOp).toHaveBeenCalledTimes(1);
		expect(fixture.api.sendOp.mock.calls[0][1]).toMatchObject({
			type: 'item.add',
			list_uid: list.uid,
			name: 'Oat Milk'
		});
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});
