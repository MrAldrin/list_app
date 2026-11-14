// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it } from 'vitest';
import { makeFeed, makeList, waitFor } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button } from '#lib/test-support/dom.ts';
import ListMenu from './ListMenu.svelte';

it('offline_share_hint_is_linked_and_clears_when_online', async () => {
	const list = makeList();
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list] }));
	await fixture.offline();
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ListMenu, {
		target,
		props: { room: fixture.room, list, canReset: false }
	});
	try {
		flushSync();
		const opener = button(target, 'List menu');
		const menu = target.querySelector<HTMLElement>('[popover]')!;
		expect(opener.getAttribute('popovertarget')).toBe(menu.id);
		expect(menu.getAttribute('popover')).toBe('auto');
		// happy-dom does not implement native popover opening or Escape.
		// Deliver the browser boundary's toggle event; prove our response only.
		menu.dispatchEvent(Object.assign(new Event('toggle'), { newState: 'open' }));
		flushSync();
		expect(opener.getAttribute('aria-expanded')).toBe('true');
		const share = button(menu, 'Share List');
		expect(share.disabled).toBe(true);
		const id = share.getAttribute('aria-describedby');
		expect(id).toBeTruthy();
		const hint = document.getElementById(id!);
		expect(hint?.textContent).toBe('Needs a connection');
		expect(menu.contains(hint)).toBe(true);
		expect(share.title).toBe('Needs a connection');
		menu.dispatchEvent(Object.assign(new Event('toggle'), { newState: 'closed' }));
		flushSync();
		expect(opener.getAttribute('aria-expanded')).toBe('false');
		fixture.online();
		await waitFor(() => expect(fixture.room.store.canWrite).toBe(true));
		flushSync();
		expect(share.disabled).toBe(false);
		expect(share.hasAttribute('aria-describedby')).toBe(false);
		expect(share.title).toBe('');
		expect(document.getElementById(id!)).toBeNull();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});
