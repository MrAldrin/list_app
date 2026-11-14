// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { afterEach, expect, it, vi } from 'vitest';
import type { Item, RoomHandle } from '#lib/data/index.ts';
import { createRoomStore } from '#lib/data/room-store.svelte.ts';
import { applied, makeFeed, makeItem, makeList, ROOM, waitFor } from '#lib/data/test-helpers.ts';
import ListView from './ListView.svelte';
import ListHarness from '#lib/test-support/ListHarness.svelte';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button, click, fill, rowNames, submit } from '#lib/test-support/dom.ts';
import { toasts } from '#lib/ui/toasts.svelte.ts';
import { MemoryQueueStorage } from '#lib/data/queue-storage.ts';
import { HOLD_MS } from './hold-order.ts';
import { readyShare } from '#lib/test-support/share-fixture.ts';

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
});

vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost/list/test') } }));
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
