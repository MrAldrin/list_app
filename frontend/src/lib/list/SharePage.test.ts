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
import { SHARE_RESET_MESSAGE } from './items.ts';

vi.mock('$app/state', async () => {
	const { reactive } = await import('#lib/test-support/reactive.svelte.ts');
	return { page: reactive({ params: { token: '' }, url: new URL('http://localhost/share/test') }) };
});
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('#lib/data/index.ts', async (original) => ({
	...(await original<typeof data>()),
	openShare: vi.fn(),
	closeShare: (room: data.RoomHandle) => room.release()
}));

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
