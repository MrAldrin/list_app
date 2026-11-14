// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import {
	makeFeed,
	makeItem,
	makeList,
	FakeEventSource,
	json,
	waitFor
} from '#lib/data/test-helpers.ts';
import type * as data from '#lib/data/index.ts';
import { MemoryQueueStorage } from '#lib/data/queue-storage.ts';
import SharePage from './share/[token]/+page.svelte';

const token = 'v'.repeat(43);
vi.mock('$app/state', () => ({
	page: {
		params: { token: 'v'.repeat(43) },
		url: new URL(`http://localhost/share/${'v'.repeat(43)}`)
	}
}));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('#lib/data/index.ts', async (original) => {
	const actual = await original<typeof data>();
	return {
		...actual,
		// Keep the real factory and its share adapter. Inject only device and
		// live-network boundaries; HTTP still goes through the real API client.
		openShare: (token: string, options: data.RoomOptions) =>
			actual.openShare(token, {
				...options,
				snapshotStore: null,
				sessionLocks: null,
				queueStorage: new MemoryQueueStorage(),
				visibility: null,
				online: null,
				createEventSource: (url) => new FakeEventSource(url)
			})
	};
});

it('fresh visitor renders shared list without room login', async () => {
	const list = makeList({ slug: '' });
	const feed = makeFeed({ full: true, room: null, lists: [list], items: [makeItem(list.uid)] });
	const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
		expect(input).toBe(`/api/v1/share/${token}/changes?since=0`);
		expect(init).toMatchObject({ method: 'GET', credentials: 'same-origin' });
		return json(200, feed);
	});
	vi.stubGlobal('fetch', fetch);
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(SharePage, { target });
	try {
		await waitFor(() => expect(fetch).toHaveBeenCalled());
		await waitFor(() => {
			flushSync();
			expect(target.textContent).not.toContain('Loading…');
		});
		expect(target.querySelector('h1')?.textContent).toBe('Groceries');
		expect(target.querySelector('input[aria-label="Add or Search"]')).not.toBeNull();
		expect(target.querySelector('button.name')?.textContent).toContain('milk');
		expect(target.querySelector('#room-password')).toBeNull();
		expect(target.textContent).not.toContain('Room Password');
		expect(target.querySelector('a[aria-label="Back to room"]')).toBeNull();
	} finally {
		await unmount(component);
		target.remove();
		vi.unstubAllGlobals();
	}
});
