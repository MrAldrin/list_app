// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it } from 'vitest';
import { makeFeed, makeItem, makeList, waitFor } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { click } from '#lib/test-support/dom.ts';
import SavedChanges from './SavedChanges.svelte';

it('deleted_edit_has_no_save_mine_and_dismiss_closes_sheet', async () => {
	const list = makeList();
	const milk = makeItem(list.uid);
	const device = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(SavedChanges, { target, props: { room: device.room } });
	try {
		await device.offline();
		await device.room.editItem(milk, { name: 'whole milk', description: '' });
		await waitFor(async () => expect(await device.queue.read()).toHaveLength(1));
		device.api.sendOp.mockImplementation(async (_slug, op) => ({
			op_id: op.op_id,
			status: 'rejected',
			code: 'item_not_found',
			message: 'Item deleted',
			seq: 2
		}));
		device.setFeed(makeFeed({ seq: 2, full: true, lists: [list], items: [] }));
		device.online();
		await waitFor(() => {
			flushSync();
			expect(target.textContent).toContain('1 change was not saved');
		});
		click(target, 'Review');
		expect(target.querySelector('dialog p')?.textContent).toBe(
			"Edit 'milk': it was deleted by someone else."
		);
		expect(
			[...target.querySelectorAll('button')].some(
				(node) => node.textContent?.trim() === 'Save mine anyway'
			)
		).toBe(false);
		click(target.querySelector('dialog')!, 'Dismiss');
		expect(target.querySelector('dialog')).toBeNull();
		expect(target.querySelector('.banner')).toBeNull();
		expect(device.room.store.notSaved).toEqual([]);
		await waitFor(async () => expect(await device.queue.readNotSaved()).toEqual([]));
	} finally {
		await unmount(component);
		device.room.release();
		target.remove();
	}
});
