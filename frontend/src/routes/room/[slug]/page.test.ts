// @vitest-environment happy-dom
import { IDBFactory } from 'fake-indexeddb';
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import * as data from '#lib/data/index.ts';
import { ApiError } from '#lib/data/types.ts';
import { createSnapshotStore } from '#lib/data/snapshot-store.ts';
import { MemoryQueueStorage } from '#lib/data/queue-storage.ts';
import { fakeRoomApi, FakeEventSource, ROOM, waitFor } from '#lib/data/test-helpers.ts';
import RoomPage from './+page.svelte';

vi.mock('$app/state', () => ({
	page: { params: { slug: 'home-ab12cd' }, url: new URL('http://localhost/room/home-ab12cd') }
}));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('#lib/data/index.ts', async (original) => ({
	...(await original<typeof data>()),
	openRoom: vi.fn()
}));

it('500 without snapshot renders load error not connect', async () => {
	const actual = await vi.importActual<typeof data>('#lib/data/index.ts');
	const snapshots = createSnapshotStore({ indexedDB: new IDBFactory(), channel: null });
	const api = fakeRoomApi();
	api.changes.mockRejectedValue(new ApiError(500, 'internal_error', 'Broken first load'));
	let room: data.RoomHandle | undefined;
	vi.mocked(data.openRoom).mockImplementation((slug, options) => {
		room = actual.openRoom(slug, {
			...options,
			api,
			snapshotStore: snapshots,
			sessionLocks: null,
			queueStorage: new MemoryQueueStorage(),
			visibility: null,
			online: null,
			createEventSource: (url) => new FakeEventSource(url)
		});
		return room;
	});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(RoomPage, { target });
	try {
		await waitFor(() => {
			flushSync();
			expect(room?.store.status).toBe('error');
		});
		expect(target.querySelector('.problem p')?.textContent).toBe('Could not load this room.');
		expect(data.openRoom).toHaveBeenCalledExactlyOnceWith(ROOM.slug, { hydrateSavedView: true });
		expect(api.whoAmI).toHaveBeenCalled();
		expect(api.changes).toHaveBeenCalledWith(ROOM.slug, 0);
		expect(room?.store.status).toBe('error');
		expect(room?.store.unreachable).toBe(false);
		expect(room?.store.savedAt).toBeNull();
		expect(await snapshots.read({ kind: 'room', slug: ROOM.slug })).toEqual({
			ok: true,
			value: null
		});
		expect(target.textContent).toContain('Broken first load');
		expect(target.textContent).not.toContain('Connect to load this room.');
		expect(target.querySelector('#room-password')).toBeNull();
	} finally {
		await unmount(component);
		snapshots.close();
		target.remove();
		vi.clearAllMocks();
	}
});
