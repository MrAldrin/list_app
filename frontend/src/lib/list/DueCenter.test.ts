// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { page } from '$app/state';
import * as data from '#lib/data/index.ts';
import { makeFeed, makeItem, makeList, ROOM, waitFor } from '#lib/data/test-helpers.ts';
import DueCenter from './DueCenter.svelte';
import ListView from './ListView.svelte';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button, click } from '#lib/test-support/dom.ts';
import { ReminderApi } from '#lib/reminders/api.ts';
import RoomPage from '../../routes/room/[slug]/+page.svelte';
import { advanceDueClock, dueClock } from './due-clock.svelte.ts';

const reminderSettings = vi.hoisted(() => ({ enabled: false }));
vi.mock('#lib/reminders/personal-reminders.ts', () => ({
	get PERSONAL_REMINDER_SETTINGS_ENABLED() {
		return reminderSettings.enabled;
	}
}));

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

it.each(['DueCenter', 'public ListView'] as const)(
	'public scope shows only shared list and no private controls: %s',
	async (composition) => {
		reminderSettings.enabled = true;
		const previousNow = dueClock.now;
		advanceDueClock(new Date('2026-11-02T12:00:00Z'));
		const shared = makeList({ slug: '' });
		const privateList = makeList({ name: 'Chores', slug: 'chores-abc123' });
		const fixture = await readyRoom(
			makeFeed({
				full: true,
				room: null,
				lists: [shared, privateList],
				items: [
					makeItem(shared.uid, { name: 'milk', date: '2026-11-02' }),
					makeItem(privateList.uid, { name: 'dishes', date: '2026-11-02' })
				]
			})
		);
		Object.assign(page, { url: new URL('http://localhost/share/public-token') });
		const target = document.createElement('div');
		document.body.append(target);
		const component =
			composition === 'DueCenter'
				? mount(DueCenter, {
						target,
						props: { room: fixture.room, listUid: shared.uid, roomScope: false }
					})
				: mount(ListView, {
						target,
						props: { room: fixture.room, list: shared, roomHref: null, canReset: false }
					});
		try {
			flushSync();
			expect(button(target, 'Due items: 1 due, 0 overdue')).toBeDefined();
			click(target, 'Due items: 1 due, 0 overdue');
			expect(
				[...target.querySelectorAll('dialog .due-row .name')].map((node) => node.textContent)
			).toEqual(['milk']);
			const href = new URL(target.querySelector<HTMLAnchorElement>('dialog .due-row')!.href);
			expect(href.pathname).toBe('/share/public-token');
			expect(href.searchParams.get('item')).toBe(fixture.room.store.itemsOf(shared.uid)[0].uid);
			expect(Number(href.searchParams.get('at'))).toBeGreaterThan(0);
			expect(target.querySelector('dialog')?.textContent).not.toContain('dishes');
			expect(target.querySelector('dialog')?.textContent).not.toContain('Chores');
			expect(target.querySelector('dialog')?.textContent).not.toMatch(
				/Room reminder policy|List reminder policy|Reminder settings/
			);
			expect(target.querySelector('[aria-label="Room menu"]')).toBeNull();
			expect(target.querySelector('dialog [aria-label^="Private reminder settings"]')).toBeNull();
			expect(
				[...target.querySelectorAll('dialog button')].some(
					(node) => node.textContent?.trim() === 'Whole room'
				)
			).toBe(false);
		} finally {
			await unmount(component);
			fixture.room.release();
			target.remove();
			reminderSettings.enabled = false;
			advanceDueClock(previousNow);
		}
	}
);

it('last dated list deletion clears room bell', async () => {
	const previousNow = dueClock.now;
	vi.setSystemTime(new Date('2026-11-02T12:00:00Z'));
	advanceDueClock(new Date());
	const enrollment = vi
		.spyOn(ReminderApi.prototype, 'enrollment')
		.mockResolvedValue({ enrollment: { state: 'not_enrolled', revision: null } });
	const list = makeList();
	const milk = makeItem(list.uid, { date: '2026-11-02' });
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	vi.mocked(data.openRoom).mockImplementation(() => {
		fixture.room.retain();
		return fixture.room;
	});
	Object.assign(page.params, { slug: ROOM.slug });
	Object.assign(page, { url: new URL(`http://localhost/room/${ROOM.slug}`) });
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(RoomPage, { target });
	try {
		flushSync();
		click(target, 'Due items: 1 due, 0 overdue');
		expect(target.querySelector('dialog .due-row .name')?.textContent).toBe('milk');
		fixture.setFeed(
			makeFeed({
				seq: 2,
				deletions: [
					{ kind: 'list', uid: list.uid },
					{ kind: 'item', uid: milk.uid }
				]
			})
		);
		fixture.stream().seq(2);
		await waitFor(() => expect(fixture.room.store.seq).toBe(2));
		flushSync();
		expect(button(target, 'Due items: none due')).toBeDefined();
		expect(target.querySelector('.bell .badge')).toBeNull();
		expect(target.querySelector('dialog .due-row')).toBeNull();
		expect(target.querySelector('dialog')?.textContent).toContain(
			'No dated items. Add a date to an item to see it here.'
		);
		expect(fixture.room.store.lists).toEqual([]);
		expect(fixture.room.store.item(milk.uid)).toBeUndefined();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
		enrollment.mockRestore();
		vi.useRealTimers();
		advanceDueClock(previousNow);
		vi.clearAllMocks();
	}
});

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
