// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import type { Item, RoomHandle } from '#lib/data/index.ts';
import { createRoomStore } from '#lib/data/room-store.svelte.ts';
import { makeFeed, makeItem, makeList, ROOM, waitFor } from '#lib/data/test-helpers.ts';
import ListView from './ListView.svelte';

vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost/list/test') } }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

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
