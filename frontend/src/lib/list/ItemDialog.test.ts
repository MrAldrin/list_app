// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { makeItem, makeList } from '#lib/data/test-helpers.ts';
import type { RoomHandle } from '#lib/data/index.ts';
import ItemDialog from './ItemDialog.svelte';

it('keeps due editing available while personal reminder settings are hidden', async () => {
	const list = makeList();
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ItemDialog, {
		target,
		props: {
			item: makeItem(list.uid, { date: '2026-11-02', due_time: '12:00', due_timezone: 'UTC' }),
			reminderRoom: {} as RoomHandle,
			itemTags: [],
			tags: [],
			tagSettings: list.tag_settings,
			canEdit: true,
			onSave: vi.fn(),
			onTag: vi.fn(),
			onDelete: vi.fn(),
			onClose: vi.fn()
		}
	});
	flushSync();
	expect(target.querySelector('input[type="date"]')).not.toBeNull();
	expect(target.textContent).toContain('Due time (optional)');
	expect(target.textContent).not.toContain('Personal reminders for this item');
	await unmount(component);
	target.remove();
});
