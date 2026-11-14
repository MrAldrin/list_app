// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { page } from '$app/state';
import * as data from '#lib/data/index.ts';
import { ShareApi } from '#lib/data/share.ts';
import { MemoryQueueStorage } from '#lib/data/queue-storage.ts';
import {
	applied,
	deferred,
	FakeEventSource,
	makeFeed,
	makeItem,
	makeList,
	waitFor
} from '#lib/data/test-helpers.ts';
import { button, click, fill, submit } from '#lib/test-support/dom.ts';
import SharePage from '../../routes/share/[token]/+page.svelte';
import { SHARE_RESET_MESSAGE, SHARE_UNAVAILABLE_MESSAGE } from './items.ts';
import RoomListPage from '../../routes/room/[slug]/list/[list]/+page.svelte';
import Toast from '#lib/ui/Toast.svelte';
import { toasts } from '#lib/ui/toasts.svelte.ts';
import { readyShare } from '#lib/test-support/share-fixture.ts';
import { fakeRoomApi, ROOM } from '#lib/data/test-helpers.ts';

vi.mock('$app/state', async () => {
	const { reactive } = await import('#lib/test-support/reactive.svelte.ts');
	return { page: reactive({ params: { token: '' }, url: new URL('http://localhost/share/test') }) };
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('#lib/data/index.ts', async (original) => ({
	...(await original<typeof data>()),
	openShare: vi.fn(),
	closeShare: (room: data.RoomHandle) => room.release(),
	openRoom: vi.fn(),
	closeRoom: (room: data.RoomHandle) => room.release()
}));

it.each([
	['truncated', 'a'.repeat(42)],
	['unknown-43-char', 'x'.repeat(43)],
	['list-slug', 'groceries-1a2b3c']
])(
	'invalid links show generic unavailable without contents or editor: %s',
	async (_kind, token) => {
		const read = vi.fn(async () => {
			throw new data.ApiError(401, 'share_unavailable', 'Do not expose internal details.');
		});
		const handle = new data.RoomHandle(token, {
			api: new ShareApi({
				shareChanges: read,
				sendShareOp: vi.fn(),
				shareEventsUrl: (value) => `/api/v1/share/${value}/events`,
				resetShareLink: vi.fn()
			}),
			snapshotStore: null,
			sessionLocks: null,
			queueStorage: new MemoryQueueStorage(),
			visibility: null,
			online: null,
			createEventSource: (url) => new FakeEventSource(url)
		});
		vi.mocked(data.openShare).mockImplementation(() => {
			handle.retain();
			return handle;
		});
		Object.assign(page.params, { token });
		const target = document.createElement('div');
		document.body.append(target);
		const component = mount(SharePage, { target });
		try {
			await waitFor(() => expect(handle.store.status).toBe('auth_required'));
			flushSync();
			expect(read).toHaveBeenCalledWith(token, 0);
			expect(data.openShare).toHaveBeenLastCalledWith(token, { hydrateSavedView: true });
			expect(target.querySelector('.problem p')?.textContent).toBe(SHARE_UNAVAILABLE_MESSAGE);
			expect(target.textContent).not.toContain('Do not expose internal details.');
			expect(target.textContent).not.toContain('secret');
			expect(target.querySelector('ul.items')).toBeNull();
			expect(target.querySelector('input[aria-label="Add or Search"]')).toBeNull();
			expect(target.querySelector('#room-password')).toBeNull();
		} finally {
			await unmount(component);
			target.remove();
			vi.clearAllMocks();
		}
	}
);

it('visitor tags work without room management', async () => {
	let list = makeList({ slug: '' });
	const milk = makeItem(list.uid);
	let seq = 1;
	const feed = () => makeFeed({ full: true, room: null, seq, lists: [list], items: [milk] });
	const guest = await readyShare(feed());
	guest.api.sendShareOp.mockImplementation(async (_token, op) => {
		if (op.type !== 'list.tag_add' && op.type !== 'list.tag_remove')
			throw new Error(`Unexpected ${op.type}`);
		seq += 1;
		list = { ...list, changed_seq: seq, tags: op.type === 'list.tag_add' ? [op.tag] : [] };
		guest.setFeed(feed());
		return applied(op, seq);
	});
	vi.mocked(data.openShare).mockImplementation(() => {
		guest.room.retain();
		return guest.room;
	});
	Object.assign(page.params, { token: 'public-token' });
	const target = document.createElement('div');
	document.body.append(target);
	const toast = mount(Toast, { target });
	let component = mount(SharePage, { target });
	let privateRoom: data.RoomHandle | undefined;
	try {
		await waitFor(() => {
			flushSync();
			expect(target.querySelector('button.name')).not.toBeNull();
		});
		click(target, 'Options');
		click(target, 'Tags');
		fill(target.querySelector('input[aria-label="Add tag"]')!, 'produce');
		submit(target.querySelector('dialog')!);
		await waitFor(() => expect(guest.api.sendShareOp).toHaveBeenCalledTimes(1));
		await waitFor(() => expect(guest.room.waitingCount).toBe(0));
		click(target.querySelector('dialog')!, 'Close');
		expect(button(target.querySelector('ul.chips')!, 'produce')).toBeDefined();
		click(target.querySelector('ul.chips')!, 'produce');
		click(target.querySelector('dialog')!, 'Delete tag');
		await waitFor(() => expect(guest.api.sendShareOp).toHaveBeenCalledTimes(2));
		await waitFor(() => expect(guest.room.waitingCount).toBe(0));
		flushSync();
		expect(guest.api.sendShareOp.mock.calls.map(([token, op]) => [token, op])).toEqual([
			[
				'public-token',
				{ op_id: expect.any(String), type: 'list.tag_add', list_uid: list.uid, tag: 'produce' }
			],
			[
				'public-token',
				{ op_id: expect.any(String), type: 'list.tag_remove', list_uid: list.uid, tag: 'produce' }
			]
		]);
		expect(target.querySelector('ul.chips')).toBeNull();
		expect(target.textContent).toContain('Deleted tag produce');
		expect(button(target, 'Share List')).toBeDefined();
		for (const label of ['Rename Groceries', 'Delete Groceries', 'Reset share link', 'Room menu'])
			expect(
				[...target.querySelectorAll('button')].some(
					(node) => node.textContent?.trim() === label || node.getAttribute('aria-label') === label
				),
				label
			).toBe(false);
		expect(
			[...target.querySelectorAll('button')].some((node) =>
				/^Rename/.test(node.getAttribute('aria-label') ?? node.textContent?.trim() ?? '')
			)
		).toBe(false);
		expect(target.querySelector('input[aria-label="List name" i]')).toBeNull();
		expect(
			[...target.querySelectorAll('label')].some((node) =>
				/^List name$/i.test(node.textContent?.trim() ?? '')
			)
		).toBe(false);
		expect(guest.room.store.lists[0].name).toBe('Groceries');
		expect(target.querySelector('a[aria-label="Back to room"]')).toBeNull();
		expect(guest.api.resetShareLink).not.toHaveBeenCalled();

		await unmount(component);
		const api = fakeRoomApi();
		api.whoAmI.mockRejectedValue(new data.ApiError(401, 'not_authenticated', 'Sign in.'));
		api.changes.mockRejectedValue(new data.ApiError(401, 'not_authenticated', 'Sign in.'));
		privateRoom = new data.RoomHandle(ROOM.slug, {
			api,
			snapshotStore: null,
			sessionLocks: null,
			queueStorage: new MemoryQueueStorage(),
			visibility: null,
			online: null,
			createEventSource: (url) => new FakeEventSource(url)
		});
		vi.mocked(data.openRoom).mockImplementation(() => {
			privateRoom!.retain();
			return privateRoom!;
		});
		Object.assign(page.params, { slug: ROOM.slug, list: 'groceries-1a2b3c' });
		component = mount(RoomListPage, { target });
		await waitFor(() => expect(privateRoom!.store.status).toBe('auth_required'));
		flushSync();
		expect(target.querySelector('#room-password')).not.toBeNull();
		expect(target.textContent).toContain('Room Password');
		expect(target.textContent).not.toContain('milk');
		expect(target.querySelector('input[aria-label="Add or Search"]')).toBeNull();
	} finally {
		await unmount(component);
		await unmount(toast);
		guest.room.release();
		for (const item of toasts.items) toasts.dismiss(item.id);
		target.remove();
		vi.clearAllMocks();
	}
});

it.each(['item edit', 'tag'] as const)(
	'stale %s dialog sends then shows reset on 401',
	async (kind) => {
		const list = makeList({ slug: '' });
		const item = makeItem(list.uid);
		let feed = makeFeed({ full: true, room: null, lists: [list], items: [item] });
		const answer = deferred<data.OpResponse>();
		const send = vi.fn<(token: string, op: data.SentOp) => Promise<data.OpResponse>>(
			async () => answer.promise
		);
		const shared = (token: string) => {
			const room = new data.RoomHandle(token, {
				api: new ShareApi({
					shareChanges: vi.fn(async () => feed),
					sendShareOp: send,
					shareEventsUrl: (value) => `/share/${value}/events`,
					resetShareLink: vi.fn()
				}),
				snapshotStore: null,
				sessionLocks: null,
				queueStorage: new MemoryQueueStorage(),
				visibility: null,
				online: null,
				createEventSource: (url) => new FakeEventSource(url)
			});
			room.retain();
			return room;
		};
		const stale = shared('old-token');
		vi.mocked(data.openShare).mockReturnValue(stale);
		Object.assign(page.params, { token: 'old-token' });
		const target = document.createElement('div');
		document.body.append(target);
		let component = mount(SharePage, { target });
		try {
			await waitFor(() => {
				flushSync();
				expect(target.querySelector('button.name')).not.toBeNull();
			});
			if (kind === 'item edit') {
				(target.querySelector('button.name') as HTMLButtonElement).click();
				flushSync();
				fill(target.querySelector('dialog input')!, 'forbidden edit');
			} else {
				click(target, 'Options');
				click(target, 'Tags');
				fill(target.querySelector('input[aria-label="Add tag"]')!, 'revoked tag');
			}
			submit(target.querySelector('dialog')!);
			await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
			const sent = send.mock.calls[0];
			expect(sent[0]).toBe('old-token');
			const { op_id, ...body } = sent[1];
			expect(op_id).toEqual(expect.any(String));
			expect(body).toEqual(
				kind === 'item edit'
					? {
							type: 'item.edit',
							list_uid: list.uid,
							item_uid: item.uid,
							name: 'forbidden edit',
							description: '',
							quantity: 1,
							date: null,
							due_time: null,
							due_timezone: null,
							base_seq: 1
						}
					: { type: 'list.tag_add', list_uid: list.uid, tag: 'revoked tag' }
			);
			// No stream event: the write's 401 alone must remove the editor.
			answer.reject(new data.ApiError(401, 'share_unavailable', SHARE_RESET_MESSAGE));
			await waitFor(() => {
				flushSync();
				expect(target.textContent).toContain(SHARE_RESET_MESSAGE);
			});
			expect(target.querySelector('dialog')).toBeNull();
			expect(target.querySelector('button.name')).toBeNull();
			expect(stale.store.itemsOf(list.uid)).toEqual([]);
			await unmount(component);

			const current = shared('new-token');
			vi.mocked(data.openShare).mockReturnValue(current);
			Object.assign(page.params, { token: 'new-token' });
			send.mockImplementation(async (_token, op) => {
				expect(op).toMatchObject({ type: 'list.tag_add', tag: 'current tag' });
				feed = { ...feed, seq: 2, lists: [{ ...list, tags: ['current tag'], changed_seq: 2 }] };
				return applied(op, 2);
			});
			component = mount(SharePage, { target });
			await waitFor(() => {
				flushSync();
				expect(target.querySelector('button.name')).not.toBeNull();
			});
			click(target, 'Options');
			click(target, 'Tags');
			fill(target.querySelector('input[aria-label="Add tag"]')!, 'current tag');
			submit(target.querySelector('dialog')!);
			await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
			await waitFor(() => expect(current.waitingCount).toBe(0));
			flushSync();
			expect(current.store.lists[0].tags).toEqual(['current tag']);
			expect(send.mock.calls[1][0]).toBe('new-token');
			click(target.querySelector('dialog')!, 'Close');
			expect(button(target.querySelector('ul.chips')!, 'current tag')).toBeDefined();
			expect(data.openShare).toHaveBeenLastCalledWith('new-token', { hydrateSavedView: true });
		} finally {
			await unmount(component);
			stale.release();
			target.remove();
			vi.clearAllMocks();
		}
	}
);
