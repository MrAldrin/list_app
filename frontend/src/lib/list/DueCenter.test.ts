// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { page } from '$app/state';
import * as data from '#lib/data/index.ts';
import { makeFeed, makeItem, makeList, ROOM } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button, click } from '#lib/test-support/dom.ts';
import { ReminderApi } from '#lib/reminders/api.ts';
import RoomPage from '../../routes/room/[slug]/+page.svelte';
import { advanceDueClock, dueClock } from './due-clock.svelte.ts';

vi.mock('$app/state', async () => {
	const { reactive } = await import('#lib/test-support/reactive.svelte.ts');
	return {
		page: reactive({
			params: { slug: 'home-ab12cd' },
			url: new URL('http://localhost/room/home-ab12cd')
		})
	};
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('#lib/data/index.ts', async (original) => ({
	...(await original<typeof data>()),
	openRoom: vi.fn(),
	closeRoom: (room: data.RoomHandle) => room.release()
}));

it('current room handle cannot count another room store, including after switching rooms', async () => {
	const previousNow = dueClock.now;
	vi.setSystemTime(new Date('2026-11-02T12:00:00Z'));
	advanceDueClock(new Date());
	const enrollment = vi
		.spyOn(ReminderApi.prototype, 'enrollment')
		.mockResolvedValue({ enrollment: { state: 'not_enrolled', revision: null } });
	const homeList = makeList();
	const cabinList = makeList({ name: 'Chores', slug: 'chores-abc123' });
	const cabinRoom = { slug: 'cabin-abc123', name: 'Cabin' };
	const home = await readyRoom(
		makeFeed({
			full: true,
			lists: [homeList],
			items: [makeItem(homeList.uid, { name: 'milk', date: '2026-11-02' })]
		})
	);
	const cabin = await readyRoom(
		makeFeed({
			full: true,
			room: cabinRoom,
			lists: [cabinList],
			items: [
				makeItem(cabinList.uid, { name: 'cabin-item', date: '2026-11-02' }),
				makeItem(cabinList.uid, { name: 'cabin-second', date: '2026-11-02' })
			]
		})
	);
	vi.mocked(data.openRoom).mockImplementation((slug) => {
		const room = slug === ROOM.slug ? home.room : cabin.room;
		room.retain();
		return room;
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(RoomPage, { target });
	const switchTo = (slug: string) => {
		Object.assign(page.params, { slug });
		Object.assign(page, { url: new URL(`http://localhost/room/${slug}`) });
		flushSync();
	};
	try {
		flushSync();
		expect(button(target, 'Due items: 1 due, 0 overdue')).toBeDefined();
		click(target, 'Due items: 1 due, 0 overdue');
		expect([...target.querySelectorAll('dialog .due-row .name')].map((n) => n.textContent)).toEqual(
			['milk']
		);
		expect(target.querySelector('dialog .due-row')?.getAttribute('href')).toContain(
			`/room/${ROOM.slug}/`
		);
		target.querySelector('dialog')!.dispatchEvent(new Event('cancel', { cancelable: true }));
		flushSync();
		switchTo(cabinRoom.slug);
		expect(button(target, 'Due items: 2 due, 0 overdue')).toBeDefined();
		click(target, 'Due items: 2 due, 0 overdue');
		expect([...target.querySelectorAll('dialog .due-row .name')].map((n) => n.textContent)).toEqual(
			['cabin-item', 'cabin-second']
		);
		expect(target.querySelector('dialog')?.textContent).not.toContain('milk');
		target.querySelector('dialog')!.dispatchEvent(new Event('cancel', { cancelable: true }));
		flushSync();
		switchTo(ROOM.slug);
		expect(button(target, 'Due items: 1 due, 0 overdue')).toBeDefined();
		click(target, 'Due items: 1 due, 0 overdue');
		expect([...target.querySelectorAll('dialog .due-row .name')].map((n) => n.textContent)).toEqual(
			['milk']
		);
		expect(data.openRoom).toHaveBeenLastCalledWith(ROOM.slug, { hydrateSavedView: true });
	} finally {
		await unmount(component);
		home.room.release();
		cabin.room.release();
		target.remove();
		enrollment.mockRestore();
		vi.useRealTimers();
		advanceDueClock(previousNow);
		vi.clearAllMocks();
	}
});
