// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { admin } from '#lib/data/index.ts';
import { waitFor } from '#lib/data/test-helpers.ts';
import AdminPage from './admin/+page.svelte';

it('signed-out admin renders password only', async () => {
	const signedIn = vi.spyOn(admin, 'signedIn').mockResolvedValue(false);
	const rooms = vi.spyOn(admin, 'rooms');
	const invitations = vi.spyOn(admin, 'invitations');
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(AdminPage, { target });
	try {
		flushSync();
		expect(signedIn).toHaveBeenCalledTimes(1);
		await waitFor(() => {
			flushSync();
			expect(target.textContent).not.toContain('Loading…');
		});
		expect(target.querySelector('h1')?.textContent).toBe('Enter Admin Password');
		expect(target.querySelector('label')?.textContent).toBe('Admin Password');
		expect(target.querySelector('input[type="password"]')).not.toBeNull();
		expect(target.textContent).not.toMatch(/Sign out of admin|Create room|Invitations|Room logins/);
		expect(target.querySelector('a[href^="/room/"]')).toBeNull();
		expect(rooms).not.toHaveBeenCalled();
		expect(invitations).not.toHaveBeenCalled();
	} finally {
		await unmount(component);
		vi.restoreAllMocks();
		target.remove();
	}
});
