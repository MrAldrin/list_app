// @vitest-environment happy-dom
// A room outlives the page that opened it (decision 68). Its derived data must
// keep updating after that page's effects are gone. Uses runes, so the file
// name ends in `.svelte.test.ts`; the comment on the first line runs it in
// a fake browser (happy-dom), so Svelte uses its browser code with effects.

import { flushSync } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import { RoomHandle } from './index';
import { FakeEventSource, fakeRoomApi, makeFeed, makeList, ROOM } from './test-helpers';

function fakeApi() {
	return fakeRoomApi({
		changes: vi.fn(async () => makeFeed({ seq: 0, full: true })),
		sendOp: vi.fn()
	});
}

describe('room store lifetime', () => {
	it('reactively updates canWrite and readOnly when only authorization changes', () => {
		const room = new RoomHandle(ROOM.slug, {
			api: fakeApi(),
			snapshotStore: null,
			sessionLocks: null,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		room.store.applyFeed(makeFeed({ seq: 1, full: true }));
		room.store.status = 'ready';
		expect(room.store.status).toBe('ready');
		expect(room.store.error).toBeNull();
		const seen: { canWrite: boolean; readOnly: boolean }[] = [];
		const stop = $effect.root(() => {
			$effect(() => {
				seen.push({ canWrite: room.store.canWrite, readOnly: room.store.readOnly });
			});
		});
		flushSync();
		expect(seen).toEqual([{ canWrite: false, readOnly: true }]);

		room.store.setWriteAuthorized(true);
		flushSync();
		expect(seen.at(-1)).toEqual({ canWrite: true, readOnly: false });

		room.store.liveChanged('reconnecting');
		flushSync();
		expect(room.store.status).toBe('ready');
		expect(room.store.error).toBeNull();
		expect(seen.at(-1)).toEqual({ canWrite: false, readOnly: true });
		stop();
	});

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
