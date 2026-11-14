// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { json, waitFor } from '#lib/data/test-helpers.ts';
import InvitationPage from './create-room/[token]/+page.svelte';

vi.mock('$app/state', () => ({ page: { params: { token: 'active-invitation' } } }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

it('active token renders create-room form', async () => {
	const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		expect(input).toBe('/api/v1/invitations/active-invitation');
		expect(init).toMatchObject({ method: 'GET', credentials: 'same-origin' });
		return json(200, {});
	});
	vi.stubGlobal('fetch', fetch);
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(InvitationPage, { target });
	try {
		await waitFor(() => {
			flushSync();
			expect(fetch).toHaveBeenCalledTimes(1);
			expect(target.textContent).not.toContain('Loading…');
		});
		expect(target.querySelector('form h1')?.textContent).toBe('Create your room');
		const label = [...target.querySelectorAll('label')].find(
			(node) => node.textContent === 'Room name'
		)!;
		expect(label).toBeDefined();
		const input = target.querySelector<HTMLInputElement>(`#${label.htmlFor}`)!;
		expect(input.tagName).toBe('INPUT');
		expect(input.disabled).toBe(false);
		expect(target.textContent).not.toContain('This invitation is invalid or no longer active.');
		expect(fetch).toHaveBeenCalledTimes(1);
	} finally {
		await unmount(component);
		target.remove();
		vi.unstubAllGlobals();
	}
});
