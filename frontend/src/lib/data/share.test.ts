import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Api } from './api';
import { closeShare, openShare } from './index';
import { ShareApi } from './share';
import {
	applied,
	deferred,
	FakeEventSource,
	makeFeed,
	makeItem,
	makeList,
	settle,
	type Deferred
} from './test-helpers';
import { ApiError } from './types';
import type { Feed, OpResponse, SentOp } from './types';

const TOKEN = 'a'.repeat(43);
const list = makeList({ uid: 'list-a', slug: '' });
const milk = makeItem(list.uid, { uid: 'item-milk', name: 'milk' });
const UNAVAILABLE = new ApiError(
	401,
	'share_unavailable',
	'This list was deleted or this share link was reset.'
);

/** A scripted share server: one list, answered by hand. */
function fakeShareApi() {
	const feeds: (Feed | Error)[] = [
		makeFeed({ seq: 5, full: true, room: null, lists: [list], items: [milk] })
	];
	const ops: { op: SentOp; answer: Deferred<OpResponse> }[] = [];
	const api = {
		shareChanges: vi.fn(async (_token: string, since: number) => {
			const feed = feeds.shift() ?? makeFeed({ seq: since, full: true, room: null, lists: [list] });
			if (feed instanceof Error) throw feed;
			return feed;
		}),
		sendShareOp: vi.fn((_token: string, op: SentOp) => {
			const answer = deferred<OpResponse>();
			ops.push({ op, answer });
			return answer.promise;
		}),
		shareEventsUrl: (token: string) => `/api/v1/share/${token}/events`,
		resetShareLink: vi.fn(async () => ({ token: 'new' }))
	};
	return { api, feeds, ops };
}

let tokenCount = 0;

/** A new token per test: `openShare` keeps handles per token for the page's life. */
async function opened() {
	tokenCount += 1;
	const token = `${tokenCount}`.padStart(43, 't');
	const server = fakeShareApi();
	const share = openShare(token, {
		shareApi: server.api,
		createEventSource: (url) => new FakeEventSource(url),
		visibility: null
	});
	await settle();
	return { token, share, store: share.store, ...server };
}

describe('ShareApi', () => {
	it('uses the share endpoints with the token in the path', async () => {
		const fetch = vi.fn(
			async () =>
				new Response(JSON.stringify(makeFeed({ room: null })), {
					status: 200,
					headers: { 'Content-Type': 'application/json' }
				})
		);
		const shareApi = new ShareApi(new Api(fetch));
		await shareApi.changes(TOKEN, 3);
		expect(fetch).toHaveBeenCalledWith(
			`/api/v1/share/${TOKEN}/changes?since=3`,
			expect.objectContaining({ method: 'GET' })
		);
		await shareApi.sendOp(TOKEN, { op_id: 'x', type: 'list.tag_add', list_uid: 'l', tag: 't' });
		expect(fetch).toHaveBeenLastCalledWith(
			`/api/v1/share/${TOKEN}/ops`,
			expect.objectContaining({ method: 'POST' })
		);
		expect(shareApi.eventsUrl(TOKEN)).toBe(`/api/v1/share/${TOKEN}/events`);
	});

	it('shares its own link and cannot do room things', async () => {
		const fetch = vi.fn();
		const shareApi = new ShareApi(new Api(fetch));
		expect(await shareApi.shareLink(TOKEN)).toEqual({ token: TOKEN });
		for (const call of [
			() => shareApi.resetShareLink(TOKEN, 'list-a'),
			() => shareApi.login(),
			() => shareApi.changePassword(),
			() => shareApi.deleteRoom()
		]) {
			await expect(call()).rejects.toMatchObject({ status: 403 });
		}
		expect(fetch).not.toHaveBeenCalled();
	});
});

describe('ShareApi room members', () => {
	function memberApi(room: { slug: string; name: string } | null) {
		const reset = vi.fn<(slug: string, listUid: string) => Promise<{ token: string }>>(
			async () => ({ token: 'n'.repeat(43) })
		);
		const api = {
			shareChanges: vi.fn(async () => makeFeed({ room, lists: [list] })),
			sendShareOp: vi.fn(),
			shareEventsUrl: () => '',
			resetShareLink: reset
		};
		return { shareApi: new ShareApi(api), reset };
	}

	it('resets through the room endpoint when the feed named the room', async () => {
		const { shareApi, reset } = memberApi({ slug: 'home', name: 'Home' });
		await shareApi.changes(TOKEN, 0);
		expect(await shareApi.resetShareLink(TOKEN, 'list-a')).toEqual({ token: 'n'.repeat(43) });
		expect(reset).toHaveBeenCalledWith('home', 'list-a');
	});

	it('cannot reset when the feed named no room', async () => {
		const { shareApi, reset } = memberApi(null);
		await shareApi.changes(TOKEN, 0);
		await expect(shareApi.resetShareLink(TOKEN, 'list-a')).rejects.toMatchObject({ status: 403 });
		expect(reset).not.toHaveBeenCalled();
	});
});

describe('openShare', () => {
	beforeEach(() => {
		FakeEventSource.reset();
	});

	it('loads the one list by token, without a room', async () => {
		const { token, share, store, api } = await opened();
		expect(api.shareChanges).toHaveBeenCalledWith(token, 0);
		expect(store.status).toBe('ready');
		expect(store.room).toBeNull();
		expect(store.lists).toEqual([list]);
		expect(store.itemsOf(list.uid)).toEqual([milk]);
		expect(FakeEventSource.last.url).toBe(`/api/v1/share/${token}/events`);
		expect(openShare(token)).toBe(share);
		closeShare(share);
		closeShare(share);
		expect(FakeEventSource.last.closed).toBe(true);
	});

	it('writes with the token and shows the change after the feed', async () => {
		const { token, share, store, ops, feeds } = await opened();
		const result = share.setDone(milk, true);
		await settle();
		expect(ops[0].op).toMatchObject({ type: 'item.set_done', item_uid: milk.uid, done: true });
		expect(store.item(milk.uid)?.done).toBe(true);

		feeds.push(
			makeFeed({
				seq: 6,
				full: true,
				room: null,
				lists: [list],
				items: [{ ...milk, done: true, changed_seq: 6 }]
			})
		);
		ops[0].answer.resolve(applied(ops[0].op, 6));
		expect(await result).toEqual({ ok: true, result: {} });
		expect(store.item(milk.uid)?.done).toBe(true);
		expect(share.queuedOps).toHaveLength(0);
		expect(await share.shareLink(list)).toEqual({ ok: true, result: { token } });
		closeShare(share);
	});

	it('stops at a reset link: the page shows it, the write waits and is never applied', async () => {
		const { share, store, ops } = await opened();
		const result = share.addItem(list, 'bread');
		let settled = false;
		void result.then(() => (settled = true));
		await settle();
		ops[0].answer.reject(UNAVAILABLE);
		await settle();

		expect(store.status).toBe('auth_required');
		expect(share.queuedOps).toHaveLength(1);
		expect(settled).toBe(false);
		closeShare(share);
	});

	it('asks again when the stream says revoked', async () => {
		const { share, store, api, feeds } = await opened();
		FakeEventSource.last.open();
		feeds.push(UNAVAILABLE);
		FakeEventSource.last.revoked();
		await settle();

		expect(api.shareChanges).toHaveBeenCalledTimes(2);
		expect(store.status).toBe('auth_required');
		expect(FakeEventSource.last.closed).toBe(true);
		closeShare(share);
	});

	it('shows the link as unavailable when the first read finds no list', async () => {
		tokenCount += 1;
		const server = fakeShareApi();
		server.feeds.splice(0, 1, UNAVAILABLE);
		const share = openShare(`${tokenCount}`.padStart(43, 'u'), {
			shareApi: server.api,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null
		});
		await settle();
		expect(share.store.status).toBe('auth_required');
		expect(share.store.lists).toEqual([]);
		closeShare(share);
	});
});
