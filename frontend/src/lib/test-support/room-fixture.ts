// A real RoomHandle with only its network and device-storage boundaries replaced.
import { IDBFactory } from 'fake-indexeddb';
import { expect } from 'vitest';
import { RoomHandle, NetworkError, type Feed, type RoomOptions } from '#lib/data/index.ts';
import { createQueueStorage } from '#lib/data/queue-storage.ts';
import { FakeEventSource, fakeRoomApi, ROOM, waitFor } from '#lib/data/test-helpers.ts';

export async function readyRoom(initial: Feed, options: RoomOptions = {}) {
	let feed = initial;
	const api = fakeRoomApi();
	api.whoAmI.mockResolvedValue(initial.room ?? ROOM);
	api.changes.mockImplementation(async () => feed);
	const connectivity = new EventTarget();
	const queue = createQueueStorage(`room:${initial.room?.slug ?? ROOM.slug}`, {
		indexedDB: new IDBFactory()
	});
	let stream: FakeEventSource | undefined;
	const room = new RoomHandle(initial.room?.slug ?? ROOM.slug, {
		api,
		snapshotStore: null,
		sessionLocks: null,
		queueStorage: queue,
		visibility: null,
		online: connectivity,
		createEventSource: (url) => (stream = new FakeEventSource(url)),
		...options
	});
	room.retain();
	await waitFor(() => expect(room.store.canWrite).toBe(true));
	await waitFor(() => expect(stream).toBeDefined());
	return {
		room,
		api,
		queue,
		setFeed(next: Feed) {
			feed = next;
		},
		async refresh(next: Feed) {
			feed = next;
			await room.store.refresh();
		},
		async offline() {
			api.whoAmI.mockRejectedValue(new NetworkError());
			api.changes.mockRejectedValue(new NetworkError());
			api.sendOp.mockRejectedValue(new NetworkError());
			connectivity.dispatchEvent(new Event('offline'));
			// A disabled write gate alone is not a completed offline check.
			// Wait for the failed session read before a test starts its edit.
			await waitFor(() => expect(room.store.unreachable).toBe(true));
			expect(room.store.canWrite).toBe(false);
			expect(room.store.canEdit).toBe(true);
		},
		online() {
			api.whoAmI.mockResolvedValue(initial.room ?? ROOM);
			api.changes.mockImplementation(async () => feed);
			connectivity.dispatchEvent(new Event('online'));
		},
		stream: () => stream!
	};
}
