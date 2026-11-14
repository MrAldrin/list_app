// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { page } from '$app/state';
import * as data from '#lib/data/index.ts';
import { makeFeed, makeItem, makeList, ROOM, waitFor } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { ReminderApi } from '#lib/reminders/api.ts';
import RoomListPage from '../../routes/room/[slug]/list/[list]/+page.svelte';
import RoomPage from '../../routes/room/[slug]/+page.svelte';
import { DELETED_LIST_MESSAGE } from './items.ts';

vi.mock('$app/state', async () => {
	const { reactive } = await import('#lib/test-support/reactive.svelte.ts');
	return { page: reactive({ params: { slug: '', list: '' }, url: new URL('http://localhost/') }) };
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('#lib/data/index.ts', async (original) => ({
	...(await original<typeof data>()),
	openRoom: vi.fn(),
	closeRoom: (room: data.RoomHandle) => room.release()
}));

it('live deletion replaces the list with a message and room link', async () => {
	const enrollment = vi
		.spyOn(ReminderApi.prototype, 'enrollment')
		.mockResolvedValue({ enrollment: { state: 'not_enrolled', revision: null } });
	const list = makeList();
	const milk = makeItem(list.uid);
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list], items: [milk] }));
	vi.mocked(data.openRoom).mockImplementation(() => {
		fixture.room.retain();
		return fixture.room;
	});
	Object.assign(page.params, { slug: ROOM.slug, list: list.slug });
	Object.assign(page, { url: new URL(`http://localhost/room/${ROOM.slug}/list/${list.slug}`) });
	const target = document.createElement('div');
	document.body.append(target);
	let component = mount(RoomListPage, { target });
	try {
		flushSync();
		expect(target.querySelector('h1')?.textContent).toBe('Groceries');
		expect(target.querySelector('input[aria-label="Add or Search"]')).not.toBeNull();
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
		expect(target.textContent).toContain(DELETED_LIST_MESSAGE);
		expect(target.querySelector('button.name')).toBeNull();
		expect(target.querySelector('input[aria-label="Add or Search"]')).toBeNull();
		const back = [...target.querySelectorAll<HTMLAnchorElement>('a')].find(
			(node) => node.textContent?.trim() === 'Back to room'
		)!;
		expect(back.getAttribute('href')).toBe(`/room/${ROOM.slug}`);
		// Hand the actual link destination to the mounted room route. Native
		// browser navigation and SSE transport remain in retained journeys.
		const destination = new URL(back.href);
		await unmount(component);
		Object.assign(page.params, { slug: destination.pathname.split('/')[2] });
		Object.assign(page, { url: destination });
		component = mount(RoomPage, { target });
		flushSync();
		expect(target.textContent).toContain('No lists yet. Create your first one!');
		expect(target.querySelector('.list-row')).toBeNull();
		expect(data.openRoom).toHaveBeenLastCalledWith(ROOM.slug, { hydrateSavedView: true });
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
		enrollment.mockRestore();
		vi.clearAllMocks();
	}
});
