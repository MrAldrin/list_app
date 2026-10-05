// @vitest-environment happy-dom
// A room outlives the page that opened it (decision 68). Its derived data must
// keep updating after that page's effects are gone. Uses runes, so the file
// name ends in `.svelte.test.ts`; the comment on the first line runs it in
// a fake browser (happy-dom), so Svelte uses its browser code with effects.

import { flushSync } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import { RoomHandle, type RoomApi } from './index';
import { FakeEventSource, makeFeed, makeList, ROOM } from './test-helpers';

function fakeApi(): RoomApi {
	return {
		changes: vi.fn(async () => makeFeed({ seq: 0, full: true })),
		sendOp: vi.fn(),
		login: vi.fn(async () => ROOM),
		whoAmI: vi.fn(async () => ROOM),
		changePassword: vi.fn(async () => ROOM),
		deleteRoom: vi.fn(async () => undefined),
		shareLink: vi.fn(async () => ({ token: 'token' })),
		resetShareLink: vi.fn(async () => ({ token: 'token' })),
		eventsUrl: (slug: string) => `/api/v1/rooms/${slug}/events`
	};
}

describe('room store lifetime', () => {
	it('keeps derived data live after the effect that created it ends', () => {
		let room!: RoomHandle;
		const seen: string[][] = [];
		// Like the room page: the room is opened inside an effect.
		const leavePage = $effect.root(() => {
			room = new RoomHandle(ROOM.slug, {
				api: fakeApi(),
				createEventSource: (url) => new FakeEventSource(url),
				visibility: null
			});
			$effect(() => {
				seen.push(room.store.lists.map((list) => list.name));
			});
		});
		flushSync();
		room.store.applyFeed(
			makeFeed({ seq: 1, full: true, lists: [makeList({ name: 'Groceries' })] })
		);
		flushSync();
		expect(seen.at(-1)).toEqual(['Groceries']);

		leavePage();
		room.store.applyFeed(makeFeed({ seq: 2, lists: [makeList({ name: 'apples' })] }));

		expect(room.store.lists.map((list) => list.name)).toEqual(['apples', 'Groceries']);
	});
});
