// @vitest-environment happy-dom
import { flushSync, mount, tick, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import type { RoomHandle } from '#lib/data/index.ts';
import { createRoomStore } from '#lib/data/room-store.svelte.ts';
import { makeFeed, makeItem, makeList, ROOM } from '#lib/data/test-helpers.ts';
import { advanceDueClock, dueClock } from '#lib/list/due-clock.svelte.ts';
import { ReminderApi } from '#lib/reminders/api.ts';
import RoomLists from './RoomLists.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

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
