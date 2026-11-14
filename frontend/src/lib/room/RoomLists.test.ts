// @vitest-environment happy-dom
import { flushSync, mount, tick, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import type { RoomHandle } from '#lib/data/index.ts';
import { createRoomStore } from '#lib/data/room-store.svelte.ts';
import { makeFeed, makeItem, makeList, ROOM } from '#lib/data/test-helpers.ts';
import { advanceDueClock, dueClock } from '#lib/list/due-clock.svelte.ts';
import { ReminderApi } from '#lib/reminders/api.ts';
import RoomLists from './RoomLists.svelte';
import SavedChanges from './SavedChanges.svelte';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { click, fill, submit } from '#lib/test-support/dom.ts';
import { waitFor } from '#lib/data/test-helpers.ts';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

it('offline_refused_rename_restores_row_and_dismisses', async () => {
	const enrollment = vi
		.spyOn(ReminderApi.prototype, 'enrollment')
		.mockResolvedValue({ enrollment: { state: 'not_enrolled', revision: null } });
	const shopping = makeList({ name: 'Shopping' });
	const hardware = makeList({ name: 'Hardware' });
	const committed = makeFeed({ full: true, lists: [shopping, hardware] });
	const device = await readyRoom(committed);
	const target = document.createElement('div');
	document.body.append(target);
	const rows = mount(RoomLists, { target, props: { room: device.room } });
	const changes = mount(SavedChanges, { target, props: { room: device.room } });
	try {
		await device.offline();
		flushSync();
		click(target, 'Rename Hardware');
		fill(target.querySelector('dialog input')!, 'Shopping');
		submit(target.querySelector('dialog')!);
		await waitFor(() => {
			flushSync();
			expect(target.querySelector('dialog')).toBeNull();
		});
		expect(
			[...target.querySelectorAll('.list-row-link span')].map((node) => node.textContent)
		).toEqual(['Shopping', 'Shopping']);
		device.api.sendOp.mockImplementation(async (_slug, op) => ({
			op_id: op.op_id,
			status: 'rejected',
			code: 'duplicate_name',
			message: 'Name taken',
			seq: 2
		}));
		device.setFeed({ ...committed, seq: 2 });
		device.online();
		await waitFor(() => {
			flushSync();
			expect(target.textContent).toContain('1 change was not saved');
		});
		expect(
			[...target.querySelectorAll('.list-row-link span')].map((node) => node.textContent)
		).toEqual(['Hardware', 'Shopping']);
		click(target, 'Review');
		expect(target.querySelector('dialog')?.textContent).toContain(
			"Rename list to 'Shopping': that name is taken."
		);
		click(target.querySelector('dialog')!, 'Dismiss');
		expect(target.querySelector('dialog')).toBeNull();
		expect(target.textContent).not.toContain('was not saved');
		await waitFor(async () => expect(await device.queue.readNotSaved()).toEqual([]));
	} finally {
		await unmount(rows);
		await unmount(changes);
		device.room.release();
		target.remove();
		enrollment.mockRestore();
	}
});

it("shows tomorrow's milk as 1 due, not overdue, beside the Groceries link", async () => {
	const previousNow = dueClock.now;
	advanceDueClock(new Date(2026, 10, 2, 12));
	const enrollment = vi
		.spyOn(ReminderApi.prototype, 'enrollment')
		.mockResolvedValue({ enrollment: { state: 'not_enrolled', revision: null } });
	const groceries = makeList();
	const chores = makeList({ name: 'Chores', slug: 'chores-1a2b3c' });
	const store = createRoomStore(ROOM.slug, {
		changes: vi.fn().mockResolvedValue(
			makeFeed({
				full: true,
				lists: [groceries, chores],
				items: [
					makeItem(groceries.uid, { name: 'milk', date: '2026-11-03' }),
					makeItem(chores.uid, { name: 'dishes', date: '2026-11-01' })
				]
			})
		)
	});
	const target = document.createElement('div');
	document.body.append(target);
	let component: ReturnType<typeof mount> | undefined;
	try {
		await store.refresh();
		expect(store.status).toBe('ready');
		component = mount(RoomLists, {
			target,
			props: { room: { slug: ROOM.slug, store } as RoomHandle }
		});
		flushSync();
		await tick();

		const link = [...target.querySelectorAll('a')].find(
			(candidate) => candidate.textContent === 'Groceries'
		);
		expect(link).toBeDefined();
		const row = link!.closest('li.list-row');
		expect(row).not.toBeNull();
		expect(row!.querySelector('.due')?.textContent?.trim()).toBe('1 due');
		expect(row!.textContent).not.toContain('overdue');
	} finally {
		if (component) await unmount(component);
		target.remove();
		enrollment.mockRestore();
		advanceDueClock(previousNow);
	}
});
