// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { makeFeed } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { button } from '#lib/test-support/dom.ts';
import RoomHeader from './RoomHeader.svelte';

vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost/room/home-ab12cd') } }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

it('room menu and switcher keep separate entries', async () => {
	localStorage.clear();
	const fixture = await readyRoom(makeFeed({ full: true }));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(RoomHeader, { target, props: { room: fixture.room, onLogout: vi.fn() } });
	try {
		flushSync();
		const menuButton = button(target, 'Room menu');
		const menu = document.getElementById(menuButton.getAttribute('popovertarget')!)!;
		expect(menu.getAttribute('popover')).toBe('auto');
		menu.dispatchEvent(Object.assign(new Event('toggle'), { newState: 'open' }));
		flushSync();
		expect(menuButton.getAttribute('aria-expanded')).toBe('true');
		expect(button(menu, 'Share Room')).toBeDefined();
		expect(menu.querySelector('[role="group"][aria-label="Rooms"]')).toBeNull();
		expect(menu.textContent).not.toContain('Add room');
		menu.dispatchEvent(Object.assign(new Event('toggle'), { newState: 'closed' }));
		flushSync();
		expect(menuButton.getAttribute('aria-expanded')).toBe('false');
		expect(target.querySelector('h1 .name')?.textContent).toBe('Home');
		const switchButton = button(target, 'Switch room, current: Home');
		const switcher = document.getElementById(switchButton.getAttribute('popovertarget')!)!;
		expect(switcher.getAttribute('popover')).toBe('auto');
		switcher.dispatchEvent(Object.assign(new Event('toggle'), { newState: 'open' }));
		flushSync();
		expect(switchButton.getAttribute('aria-expanded')).toBe('true');
		const current = button(switcher.querySelector('[role="group"][aria-label="Rooms"]')!, 'Home');
		expect(current.getAttribute('aria-current')).toBe('true');
		expect(current.querySelector('.mark')?.textContent).toBe('✓');
		expect(button(switcher, '+ Add room')).toBeDefined();
		expect(button(switcher, 'admin')).toBeDefined();
		// PARTIAL: both current-room and admin clicks first call native
		// hidePopover. Keep those click/closure/navigation assertions in the
		// browser test, rather than supply a fake native implementation.
		switcher.dispatchEvent(Object.assign(new Event('toggle'), { newState: 'closed' }));
		flushSync();
		expect(switchButton.getAttribute('aria-expanded')).toBe('false');
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
		localStorage.clear();
		vi.clearAllMocks();
	}
});
