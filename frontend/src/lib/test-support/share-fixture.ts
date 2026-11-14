// A public composition with the real handle, share adapter, queue and store.
import { expect, vi } from 'vitest';
import { RoomHandle, type Feed } from '#lib/data/index.ts';
import { ShareApi } from '#lib/data/share.ts';
import { MemoryQueueStorage } from '#lib/data/queue-storage.ts';
import { FakeEventSource, waitFor } from '#lib/data/test-helpers.ts';

export async function readyShare(initial: Feed, token = 'public-token') {
	let feed = initial;
	const api = {
		shareChanges: vi.fn(async () => feed),
		sendShareOp: vi.fn<import('#lib/data/api.ts').Api['sendShareOp']>(async () => {
			throw new Error('Unexpected public write');
		}),
		shareEventsUrl: (value: string) => `/api/v1/share/${value}/events`,
		resetShareLink: vi.fn<import('#lib/data/api.ts').Api['resetShareLink']>(async () => {
			throw new Error('Unexpected public link reset');
		})
	};
	const room = new RoomHandle(token, {
		api: new ShareApi(api),
		snapshotStore: null,
		sessionLocks: null,
		queueStorage: new MemoryQueueStorage(),
		visibility: null,
		online: null,
		createEventSource: (url) => new FakeEventSource(url)
	});
	room.retain();
	await waitFor(() => expect(room.store.canWrite).toBe(true));
	return {
		room,
		api,
		setFeed: (next: Feed) => {
			feed = next;
		}
	};
}
