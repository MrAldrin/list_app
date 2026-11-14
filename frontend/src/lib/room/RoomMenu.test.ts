// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { makeFeed } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button, click } from '#lib/test-support/dom.ts';
import RoomMenu from './RoomMenu.svelte';
import ShareDialog from '#lib/ui/ShareDialog.svelte';
import { absoluteUrl, shareLinkWithToast } from '#lib/ui/share.ts';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

it('Share Room remains available in the room menu', async () => {
	const fixture = await readyRoom(makeFeed({ full: true, room: { slug: 'home', name: 'Home' } }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(RoomMenu, { target, props: { room: fixture.room, onLogout: vi.fn() } });
	try {
		flushSync();
		const opener = button(target, 'Room menu');
		const menu = target.querySelector<HTMLElement>('[popover]')!;
		expect(opener.getAttribute('popovertarget')).toBe(menu.id);
		menu.dispatchEvent(Object.assign(new Event('toggle'), { newState: 'open' }));
		flushSync();
		expect(opener.getAttribute('aria-expanded')).toBe('true');
		expect(button(menu, 'Share Room').disabled).toBe(false);
		// PARTIAL: clicking this entry calls native hidePopover, absent here.
		// Do not fake it. Menu-to-dialog assembly stays in the browser test.
		expect(target.querySelector('dialog')).toBeNull();
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});

it('room share fallback shows the room URL, password warning and Close callback', async () => {
	expect(typeof navigator.share).not.toBe('function');
	const url = absoluteUrl('/room/home');
	expect(await shareLinkWithToast(url, 'room')).toBe(true);
	const onClose = vi.fn();
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(ShareDialog, { target, props: { kind: 'room', url, onClose } });
	try {
		flushSync();
		expect(target.querySelector('h2')?.textContent).toBe('Share this room');
		expect(target.textContent).toContain('The recipient will also need the room password.');
		expect(target.querySelector<HTMLInputElement>('[aria-label="Link"]')?.value).toBe(
			`${window.location.origin}/room/home`
		);
		click(target, 'Close');
		expect(onClose).toHaveBeenCalledTimes(1);
	} finally {
		await unmount(component);
		target.remove();
	}
});
