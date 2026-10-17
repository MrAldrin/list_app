import { IDBFactory } from 'fake-indexeddb';
import { describe, expect, it, vi } from 'vitest';
import {
	LOCAL_SIGNOUT_TIMEOUT_MS,
	RoomHandle,
	login as standaloneLogin,
	logout as standaloneLogout,
	type RoomApi
} from './index';
import { ShareApi } from './share';
import { browserSnapshots } from './standalone-session';
import {
	FakeEventSource,
	makeFeed,
	makeItem,
	makeList,
	ROOM,
	settle,
	type Deferred
} from './test-helpers';
import { ApiError, NetworkError } from './types';
import type { Feed, Item, OpResponse, SentOp } from './types';
import { createSnapshotStore, type SnapshotStore } from './snapshot-store';
import type { SessionLockManager } from './session-transition';
import { MemoryQueueStorage, type QueueStorage } from './queue-storage';
import { newStoredEntry } from './queue-entries';

const list = makeList({ uid: 'saved-list' });
const item = makeItem(list.uid, { uid: 'saved-item', name: 'milk' });
const feed = makeFeed({ seq: 5, full: true, lists: [list], items: [item] });
let databaseCounter = 0;

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason: unknown) => void;
	const promise = new Promise<T>((resolvePromise, rejectPromise) => {
		resolve = resolvePromise;
		reject = rejectPromise;
	});
	return { promise, resolve, reject };
}

function applied(op: SentOp, seq: number): OpResponse {
	return { op_id: op.op_id, status: 'applied', result: {}, seq };
}

function snapshots(): SnapshotStore {
	databaseCounter += 1;
	return createSnapshotStore({
		indexedDB: new IDBFactory(),
		databaseName: `offline-integration-${databaseCounter}`,
		channel: null,
		now: () => new Date('2026-10-06T18:00:00.000Z')
	});
}

function sharedMemorySnapshots(): SnapshotStore {
	const listeners = new Set<
		(hint: { identity: { kind: 'room'; slug: string }; generation: number }) => void
	>();
	let generation = 0;
	return {
		generation: async (identity: { kind: 'room'; slug: string }) => ({
			ok: true as const,
			value: { identityKey: `room:${identity.slug}`, generation }
		}),
		read: async () => ({ ok: true as const, value: null }),
		save: async () => ({ ok: false as const, reason: 'unavailable' as const }),
		clear: async (identity: { kind: 'room'; slug: string }) => {
			generation += 1;
			for (const listener of listeners) listener({ identity, generation });
			return { ok: true as const, value: undefined };
		},
		localSignOut: async (identity: { kind: 'room'; slug: string }) => {
			generation += 1;
			for (const listener of listeners) listener({ identity, generation });
			return { ok: true as const, value: undefined };
		},
		prune: async () => ({ ok: true as const, value: 0 }),
		pendingServerLogouts: async () => ({ ok: true as const, value: [] }),
		acknowledgeServerLogout: async () => ({ ok: true as const, value: undefined }),
		clearSignOutAfterSignIn: async () => ({ ok: true as const, value: undefined }),
		lastRoom: async () => ({ ok: true as const, value: null }),
		onClear: (
			listener: (hint: { identity: { kind: 'room'; slug: string }; generation: number }) => void
		) => {
			listeners.add(listener);
			return () => listeners.delete(listener);
		},
		close: () => listeners.clear()
	} as unknown as SnapshotStore;
}

function fakeApi(changes: () => Promise<Feed> = async () => feed) {
	return {
		changes: vi.fn(changes),
		sendOp: vi.fn(async (...args: Parameters<RoomApi['sendOp']>): Promise<OpResponse> => {
			void args;
			return {
				op_id: 'unexpected',
				status: 'applied',
				result: {},
				seq: 6
			};
		}),
		login: vi.fn(async () => ROOM),
		logout: vi.fn(async () => undefined),
		whoAmI: vi.fn(async () => ROOM),
		changePassword: vi.fn(async () => ROOM),
		deleteRoom: vi.fn(async () => undefined),
		shareLink: vi.fn(async () => ({ token: 'share-token' })),
		resetShareLink: vi.fn(async () => ({ token: 'new-token' })),
		eventsUrl: (slug: string) => `/api/v1/rooms/${slug}/events`
	} satisfies RoomApi;
}

function handle(
	api: RoomApi,
	storage: SnapshotStore,
	extra: {
		hydrateSavedView?: boolean;
		connectivity?: Pick<Window, 'addEventListener' | 'removeEventListener'> | null;
		sessionLocks?: SessionLockManager | null;
		queueStorage?: QueueStorage;
	} = {}
) {
	const room = new RoomHandle(ROOM.slug, {
		api,
		snapshotStore: storage,
		sessionLocks: extra.sessionLocks === undefined ? serialLocks() : extra.sessionLocks,
		hydrateSavedView: extra.hydrateSavedView,
		createEventSource: (url) => new FakeEventSource(url),
		visibility: null,
		online: extra.connectivity ?? null,
		queueStorage: extra.queueStorage
	});
	room.retain();
	return room;
}

class SerialTestLocks {
	readonly #tails = new Map<string, Promise<void>>();

	request = async <T>(
		name: string,
		_options: LockOptions,
		callback: () => Promise<T>
	): Promise<T> => {
		const previous = this.#tails.get(name) ?? Promise.resolve();
		let unlock!: () => void;
		const hold = new Promise<void>((resolve) => (unlock = resolve));
		const tail = previous.then(() => hold);
		this.#tails.set(name, tail);
		await previous;
		try {
			return await callback();
		} finally {
			unlock();
			if (this.#tails.get(name) === tail) this.#tails.delete(name);
		}
	};
}

function serialLocks(): SessionLockManager {
	return new SerialTestLocks() as unknown as SessionLockManager;
}

function fakeConnectivity() {
	const listeners = new Map<string, () => void>();
	return {
		target: {
			addEventListener: (type: string, listener: () => void) => listeners.set(type, listener),
			removeEventListener: (type: string) => listeners.delete(type)
		} as unknown as Pick<Window, 'addEventListener' | 'removeEventListener'>,
		emit: (type: 'online' | 'offline') => listeners.get(type)?.()
	};
}

describe('saved room data integration', () => {
	it('persists authorized committed data, hydrates it read-only, and blocks every shared mutation', async () => {
		const storage = snapshots();
		const onlineApi = fakeApi();
		const online = handle(onlineApi, storage);
		await settle();
		await vi.waitFor(async () => {
			const saved = await storage.read({ kind: 'room', slug: ROOM.slug });
			expect(saved.ok && saved.value?.seq).toBe(5);
		});
		expect(online.store.canWrite).toBe(true);
		online.release();

		const offlineApi = fakeApi(async () => {
			throw new NetworkError();
		});
		offlineApi.whoAmI.mockRejectedValue(new NetworkError());
		const offline = handle(offlineApi, storage, { hydrateSavedView: true });
		await vi.waitFor(() => expect(offlineApi.whoAmI).toHaveBeenCalledTimes(1));
		await settle();
		expect(offline.store.lists).toEqual([list]);
		expect(offline.store.itemsOf(list.uid)).toEqual([item]);
		expect(offline.store.savedAt).toBe('2026-10-06T18:00:00.000Z');
		expect(offline.store.readOnly).toBe(true);

		// The actions that need a connection stay refused, and nothing is sent.
		const refused = await Promise.all([
			offline.createList('new'),
			offline.changePassword('old', 'new'),
			offline.deleteRoom('password'),
			offline.resetShareLink(list)
		]);
		expect(refused.every((result) => !result.ok && result.code === 'read_only')).toBe(true);
		expect(offlineApi.changePassword).not.toHaveBeenCalled();
		expect(offlineApi.deleteRoom).not.toHaveBeenCalled();
		expect(offlineApi.resetShareLink).not.toHaveBeenCalled();

		// Edits are queued at once and shown; they go out only when online again.
		const edits = await Promise.all([
			offline.renameRoom('new'),
			offline.renameList(list, 'new'),
			offline.addListTag(list, 'new'),
			offline.removeListTag(list, 'Lidl'),
			offline.setVisibility(list, { mode: 'all' }),
			offline.addItem(list, 'bread'),
			offline.setDone(item, true),
			offline.changeQuantity(item, 1),
			offline.editItem(item, { name: 'milk', description: 'cold' }),
			offline.toggleItemTag(item, 'new'),
			offline.deleteItem(item),
			offline.restoreItem(item.uid),
			offline.deleteList(list)
		]);
		expect(edits.every((result) => result.ok)).toBe(true);
		expect(offlineApi.sendOp).not.toHaveBeenCalled();
		expect(offline.queuedOps).toHaveLength(13);
		expect(offline.store.room?.name).toBe('new');
		expect(offline.store.lists).toEqual([]);
		offline.release();
		storage.close();
	});

	it('saves committed server state rather than an optimistic overlay', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const answer = deferred<OpResponse>();
		const sent: SentOp[] = [];
		api.sendOp.mockImplementation(async (_slug, op) => {
			sent.push(op);
			return answer.promise;
		});
		const room = handle(api, storage);
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		const change = room.setDone(item, true);
		await vi.waitFor(() => expect(sent).toHaveLength(1));
		expect(room.store.item(item.uid)?.done).toBe(true);
		const beforeAnswer = await storage.read({ kind: 'room', slug: ROOM.slug });
		expect(beforeAnswer).toMatchObject({
			ok: true,
			value: { seq: 5, items: [{ uid: item.uid, done: false }] }
		});

		const changedItem = {
			...item,
			done: true,
			completed_at: '2026-10-06T18:00:00.000Z',
			changed_seq: 6
		};
		api.changes.mockResolvedValueOnce(
			makeFeed({ seq: 6, full: true, lists: [list], items: [changedItem] })
		);
		answer.resolve(applied(sent[0], 6));
		await change;
		await vi.waitFor(async () => {
			const saved = await storage.read({ kind: 'room', slug: ROOM.slug });
			expect(saved.ok && saved.value?.seq).toBe(6);
		});
		room.release();
		storage.close();
	});

	it('does not hydrate snapshots by default and clears a snapshot after confirmed 401', async () => {
		const storage = snapshots();
		const online = handle(fakeApi(), storage);
		await settle();
		await vi.waitFor(async () => {
			const saved = await storage.read({ kind: 'room', slug: ROOM.slug });
			expect(saved.ok && saved.value).toBeTruthy();
		});
		online.release();

		const defaultApi = fakeApi(async () => {
			throw new NetworkError();
		});
		defaultApi.whoAmI.mockRejectedValue(new NetworkError());
		const defaultView = handle(defaultApi, storage);
		await vi.waitFor(() => expect(defaultApi.whoAmI).toHaveBeenCalledTimes(1));
		expect(defaultView.store.lists).toEqual([]);
		expect(defaultView.store.canWrite).toBe(false);
		defaultView.release();

		const revokedApi = fakeApi();
		revokedApi.whoAmI.mockRejectedValue(
			new ApiError(401, 'not_authenticated', 'Sign in to this room.')
		);
		const revoked = handle(revokedApi, storage, { hydrateSavedView: true });
		await vi.waitFor(() => expect(revokedApi.whoAmI).toHaveBeenCalledTimes(1));
		await settle();
		expect(revoked.store.lists).toEqual([]);
		await vi.waitFor(async () => {
			const saved = await storage.read({ kind: 'room', slug: ROOM.slug });
			expect(saved.ok && saved.value).toBeNull();
		});
		revoked.release();
		storage.close();
	});

	it('rejects a late feed after local clear without reapplying or persisting it', async () => {
		const storage = snapshots();
		let resolveFeed!: (value: Feed) => void;
		const pendingFeed = new Promise<Feed>((resolve) => (resolveFeed = resolve));
		const api = fakeApi(() => pendingFeed);
		const room = handle(api, storage, { sessionLocks: null });
		await vi.waitFor(() => expect(api.changes).toHaveBeenCalledTimes(1));

		expect(await room.logout()).toMatchObject({ ok: false, code: 'server_logout_pending' });
		resolveFeed(feed);
		await settle();
		expect(room.store.lists).toEqual([]);
		expect(room.store.canWrite).toBe(false);
		const saved = await storage.read({ kind: 'room', slug: ROOM.slug });
		expect(saved).toMatchObject({ ok: false, reason: 'signed_out' });
		room.release();
		storage.close();
	});
});

describe('clear and session boundaries', () => {
	it('keeps the room visible until the sign-out marker is stored, with writes already blocked', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const marker = deferred<{ ok: true; value: undefined }>();
		storage.localSignOut = vi.fn(() => marker.promise) as unknown as SnapshotStore['localSignOut'];
		const room = handle(api, storage);
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));

		const logout = room.logout();
		await vi.waitFor(() => expect(storage.localSignOut).toHaveBeenCalledTimes(1));
		expect(room.store.status).toBe('ready');
		expect(room.store.canWrite).toBe(false);

		marker.resolve({ ok: true, value: undefined });
		await logout;
		expect(room.store.status).toBe('auth_required');
	});

	it('keeps the room visible when a refresh finishes while the marker is being stored', async () => {
		const storage = snapshots();
		const second = deferred<Feed>();
		let calls = 0;
		const api = fakeApi(() => (++calls === 1 ? Promise.resolve(feed) : second.promise));
		const marker = deferred<{ ok: true; value: undefined }>();
		storage.localSignOut = vi.fn(() => marker.promise) as unknown as SnapshotStore['localSignOut'];
		const room = handle(api, storage);
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));

		const refreshing = room.store.refresh();
		await vi.waitFor(() => expect(api.changes).toHaveBeenCalledTimes(2));
		const logout = room.logout();
		await vi.waitFor(() => expect(storage.localSignOut).toHaveBeenCalledTimes(1));
		second.resolve(feed);
		await refreshing;
		await settle();
		expect(room.store.status).toBe('ready');

		marker.resolve({ ok: true, value: undefined });
		await logout;
		expect(room.store.status).toBe('auth_required');
		room.release();
		storage.close();
	});

	it('clears the view and reports unconfirmed when the marker never arrives', async () => {
		vi.useFakeTimers();
		try {
			const storage = snapshots();
			const api = fakeApi();
			const marker = deferred<{ ok: true; value: undefined }>();
			storage.localSignOut = vi.fn(
				() => marker.promise
			) as unknown as SnapshotStore['localSignOut'];
			const room = handle(api, storage);
			await vi.waitFor(() => expect(room.store.canWrite).toBe(true));

			const logout = room.logout();
			await vi.advanceTimersByTimeAsync(LOCAL_SIGNOUT_TIMEOUT_MS - 1);
			expect(room.store.status).toBe('ready');
			await vi.advanceTimersByTimeAsync(1);
			expect(await logout).toMatchObject({ ok: false, code: 'local_clear_unconfirmed' });
			expect(room.store.status).toBe('auth_required');
			expect(api.logout).not.toHaveBeenCalled();

			// A late answer, good or bad, changes nothing.
			marker.resolve({ ok: true, value: undefined });
			await vi.advanceTimersByTimeAsync(10);
			expect(room.store.status).toBe('auth_required');
			expect(api.logout).not.toHaveBeenCalled();
			room.release();
			storage.close();
		} finally {
			vi.useRealTimers();
		}
	});

	it('does not start a second server sign-out from its own late clear hint', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const answer = deferred<undefined>();
		api.logout.mockImplementation(() => answer.promise);
		let hint: ((hint: { identity: unknown; generation: number }) => void) | undefined;
		const onClear = storage.onClear.bind(storage);
		storage.onClear = ((listener: never) => {
			hint = listener;
			return onClear(listener);
		}) as unknown as SnapshotStore['onClear'];
		const originalSignOut = storage.localSignOut.bind(storage);
		storage.localSignOut = (async (identity: Parameters<SnapshotStore['localSignOut']>[0]) => {
			const result = await originalSignOut(identity);
			// The clear hint reaches this tab only after the call has returned.
			setTimeout(() => hint?.({ identity, generation: 1 }), 0);
			return result;
		}) as SnapshotStore['localSignOut'];
		// The first lock request (logout's own) is slow, so the hint's retry
		// would win the lock if it were allowed to start.
		const inner = serialLocks();
		let armed = false;
		const locks = {
			request: async (name: string, options: LockOptions, callback: () => Promise<unknown>) => {
				if (armed) {
					armed = false;
					await new Promise((resolve) => setTimeout(resolve, 30));
				}
				return (inner as never as { request: SessionLockManager['request'] }).request(
					name,
					options,
					callback
				);
			}
		} as unknown as SessionLockManager;
		const room = handle(api, storage, { sessionLocks: locks });
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));

		armed = true;
		const logout = room.logout();
		await vi.waitFor(() => expect(api.logout).toHaveBeenCalledTimes(1));
		await new Promise((resolve) => setTimeout(resolve, 20));
		answer.resolve(undefined);
		expect(await logout).toEqual({ ok: true, result: {} });
		expect(api.logout).toHaveBeenCalledTimes(1);
		room.release();
		storage.close();
	});

	it.each([new NetworkError(), new ApiError(503, 'unavailable', 'down')])(
		'reports a failed server sign-out as pending, with the contract code',
		async (error) => {
			const storage = snapshots();
			const api = fakeApi();
			api.logout.mockRejectedValue(error);
			const room = handle(api, storage);
			await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
			expect(await room.logout()).toMatchObject({ ok: false, code: 'server_logout_pending' });
			expect(room.store.status).toBe('auth_required');
			room.release();
			storage.close();
		}
	);

	it.each(['rejected', 'failed', 'unanswered'] as const)(
		'keeps a late %s answer out of the cleared view and notices',
		async (outcome) => {
			const storage = snapshots();
			const api = fakeApi();
			const answer = deferred<OpResponse>();
			api.sendOp.mockImplementation(() => answer.promise);
			const room = handle(api, storage);
			await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
			room.store.notify('old', 'Old item text');
			const action = room.addItem(list, 'private milk');
			await vi.waitFor(() => expect(api.sendOp).toHaveBeenCalledTimes(1));
			const original = room.queuedOps[0];
			expect(await room.logout()).toEqual({ ok: true, result: {} });
			expect(room.store.notice).toBeNull();
			if (outcome === 'rejected')
				answer.resolve({
					op_id: original.op_id,
					status: 'rejected',
					code: 'duplicate_active',
					message: 'private milk already exists',
					seq: 5
				});
			else if (outcome === 'failed')
				answer.reject(new ApiError(409, 'conflict', 'private milk conflict'));
			else answer.reject(new NetworkError());
			await settle();
			expect(room.store.notice).toBeNull();
			expect(room.store.error).toBeNull();
			expect(room.store.lists).toEqual([]);
			expect(room.store.queued).toBe(0);
			if (outcome === 'unanswered') {
				expect(room.queuedOps[0].op_id).toBe(original.op_id);
				expect(room.store.retrying).toBe(false);
			} else {
				expect(await action).toMatchObject({ ok: false, code: 'session_changed' });
				expect(room.queuedOps).toEqual([]);
			}
			room.release();
			storage.close();
		}
	);

	it('reports that persistent clearing was not confirmed when localSignOut fails', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const room = handle(api, {
			...storage,
			localSignOut: async () => ({ ok: false as const, reason: 'unavailable' as const })
		});
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		const result = await room.logout();
		expect(result).toMatchObject({ ok: false, code: 'local_clear_unconfirmed' });
		if (!result.ok) {
			expect(result.message).toContain('saved data could not be confirmed cleared');
			expect(result.message).toContain('Server sign-out was not attempted');
		}
		expect(api.logout).not.toHaveBeenCalled();
		expect(room.store.lists).toEqual([]);
		room.release();
		storage.close();
	});

	it('reports confirmed DELETE separately from failed marker acknowledgment', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const room = handle(api, {
			...storage,
			acknowledgeServerLogout: async () => ({ ok: false as const, reason: 'unavailable' as const })
		});
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		const result = await room.logout();
		expect(result).toMatchObject({ ok: false, code: 'logout_marker_unacknowledged' });
		if (!result.ok) {
			expect(result.message).toContain('Server sign-out succeeded');
			expect(result.message).toContain('cookie was cleared');
		}
		expect(api.logout).toHaveBeenCalledTimes(1);
		expect(await storage.pendingServerLogouts()).toMatchObject({
			ok: true,
			value: [{ kind: 'room', slug: ROOM.slug }]
		});
		room.release();
		storage.close();
	});

	it('does not claim complete logout without locks, and never deletes a later cookie', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const room = handle(api, storage, { sessionLocks: null });
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		const result = await room.logout();
		expect(result).toMatchObject({ ok: false, code: 'server_logout_pending' });
		expect(api.logout).not.toHaveBeenCalled();
		expect(await storage.pendingServerLogouts()).toMatchObject({
			ok: true,
			value: [{ kind: 'room', slug: ROOM.slug }]
		});
		expect(await room.login('password')).toMatchObject({ ok: false, code: 'logout_pending' });
		expect(api.login).not.toHaveBeenCalled();
		room.release();
		storage.close();
	});

	it('ignores a delayed old clear hint after a newer validated sign-in', async () => {
		const storage = snapshots();
		let hint!: { identity: { kind: 'room'; slug: string }; generation: number };
		let receive!: (value: typeof hint) => void;
		const originalOnClear = storage.onClear.bind(storage);
		const wrapped = {
			...storage,
			onClear: (listener: typeof receive) => {
				receive = listener;
				return originalOnClear((value) => {
					hint = value as typeof hint;
				});
			}
		};
		const room = handle(fakeApi(), wrapped);
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		await storage.clear({ kind: 'room', slug: ROOM.slug });
		expect(hint.generation).toBe(1);
		expect(await room.login('password')).toMatchObject({ ok: true });
		receive(hint);
		await settle();
		expect(room.store.canWrite).toBe(true);
		expect(room.store.lists).toEqual([list]);
		room.release();
		storage.close();
	});

	it('does not delete the cookie when a newer sign-in overtakes the marked logout', async () => {
		const storage = snapshots();
		const scan = storage.pendingServerLogouts.bind(storage);
		let overtaken = false;
		const wrapped = {
			...storage,
			pendingServerLogouts: async () => {
				if (!overtaken) {
					overtaken = true;
					await storage.clearSignOutAfterSignIn({ kind: 'room', slug: ROOM.slug });
				}
				return scan();
			}
		};
		const api = fakeApi();
		const room = handle(api, wrapped);
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		expect(await room.logout()).toMatchObject({ ok: false, code: 'server_logout_pending' });
		expect(api.logout).not.toHaveBeenCalled();
		room.release();
		storage.close();
	});

	it('does not report server logout when marker scan is unreadable', async () => {
		const storage = snapshots();
		const pending = storage.pendingServerLogouts.bind(storage);
		const api = fakeApi();
		const room = handle(api, {
			...storage,
			pendingServerLogouts: async () => ({ ok: false as const, reason: 'unavailable' as const })
		});
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		expect(await room.logout()).toMatchObject({ ok: false, code: 'server_logout_pending' });
		expect(api.logout).not.toHaveBeenCalled();
		expect((await pending()).ok).toBe(true);
		room.release();
		storage.close();
	});
});

describe('standalone sign-out', () => {
	it('reports local-only without locks instead of deleting an uncoordinated cookie', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', {});
		const api = fakeApi();
		const result = await standaloneLogout('standalone-room', api as never);
		expect(result).toMatchObject({ ok: false, code: 'server_logout_pending' });
		expect(api.logout).not.toHaveBeenCalled();
		vi.unstubAllGlobals();
	});

	it('serializes a plain-HTTP localhost logout request before the next sign-in', async () => {
		const locks = serialLocks();
		vi.stubGlobal('navigator', { locks });
		const api = fakeApi();
		const answer = deferred<void>();
		const order: string[] = [];
		api.logout.mockImplementation(async () => {
			order.push('DELETE');
			await answer.promise;
			order.push('ack');
		});
		api.login.mockImplementation(async () => {
			order.push('POST');
			return ROOM;
		});
		const logout = standaloneLogout('plain-http-room', api as never);
		await vi.waitFor(() => expect(order).toEqual(['DELETE']));
		const signin = standaloneLogin('plain-http-room', 'password', api as never);
		await settle();
		expect(api.login).not.toHaveBeenCalled();
		answer.resolve();
		expect(await logout).toEqual({ ok: true, result: {} });
		expect(await signin).toMatchObject({ ok: true });
		expect(order).toEqual(['DELETE', 'ack', 'POST']);
		vi.unstubAllGlobals();
	});
});

const identityOf = (slug: string) => ({ kind: 'room' as const, slug });

describe('standalone sign-in', () => {
	it('signs in and makes saved data readable again after a local sign-out', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-in-clear';
		const snapshots = browserSnapshots();
		await snapshots.localSignOut(identityOf(slug));
		const api = fakeApi();
		const result = await standaloneLogin(slug, 'password', api as never);
		expect(result).toEqual({ ok: true, result: ROOM });
		expect(api.login).toHaveBeenCalledWith(slug, 'password');
		expect((await snapshots.generation(identityOf(slug))).ok).toBe(true);
		vi.unstubAllGlobals();
	});

	it('waits for a pending server sign-out when Web Locks are missing and does not post', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', {});
		const slug = 'standalone-in-no-locks';
		const api = fakeApi();
		expect(await standaloneLogout(slug, api as never)).toMatchObject({
			ok: false,
			code: 'server_logout_pending'
		});
		const result = await standaloneLogin(slug, 'password', api as never);
		expect(result).toMatchObject({ ok: false, code: 'logout_pending' });
		expect(api.login).not.toHaveBeenCalled();
		expect(api.logout).not.toHaveBeenCalled();
		vi.unstubAllGlobals();
	});

	it('stops before posting when pending sign-out state cannot be read', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-in-unreadable';
		const snapshots = browserSnapshots();
		const spy = vi
			.spyOn(snapshots, 'pendingServerLogouts')
			.mockResolvedValueOnce({ ok: false, reason: 'unavailable' });
		const api = fakeApi();
		expect(await standaloneLogin(slug, 'password', api as never)).toMatchObject({
			ok: false,
			code: 'session_transition_unavailable'
		});
		expect(api.login).not.toHaveBeenCalled();
		spy.mockRestore();
		vi.unstubAllGlobals();
	});

	it('is interrupted when a local sign-out lands during the password request', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-in-interrupted';
		const snapshots = browserSnapshots();
		const api = fakeApi();
		api.login.mockImplementation(async () => {
			await snapshots.localSignOut(identityOf(slug));
			return ROOM;
		});
		expect(await standaloneLogin(slug, 'password', api as never)).toEqual({
			ok: false,
			code: 'signed_out',
			message: 'Room sign-in was interrupted by sign-out.'
		});
		expect((await snapshots.generation(identityOf(slug))).ok).toBe(false);
		vi.unstubAllGlobals();
	});

	it('returns the server error for a rejected password', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const api = fakeApi();
		api.login.mockRejectedValueOnce(new ApiError(401, 'invalid_credentials', 'Wrong password.'));
		expect(await standaloneLogin('standalone-in-password', 'bad', api as never)).toEqual({
			ok: false,
			code: 'invalid_credentials',
			message: 'Wrong password.'
		});
		vi.unstubAllGlobals();
	});

	it('signs out locally and best-effort on the server when state is unreadable after the password request', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-in-unreadable-after';
		const snapshots = browserSnapshots();
		const original = snapshots.pendingServerLogouts.bind(snapshots);
		const spy = vi
			.spyOn(snapshots, 'pendingServerLogouts')
			.mockImplementationOnce(original)
			.mockResolvedValueOnce({ ok: false, reason: 'unavailable' });
		const api = fakeApi();
		expect(await standaloneLogin(slug, 'password', api as never)).toMatchObject({
			ok: false,
			code: 'session_transition_unavailable'
		});
		expect(api.login).toHaveBeenCalledTimes(1);
		expect(api.logout).toHaveBeenCalledWith(slug);
		expect((await snapshots.generation(identityOf(slug))).ok).toBe(false);
		spy.mockRestore();
		vi.unstubAllGlobals();
	});
	it('signs out locally and on the server when the state read throws after the password request', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-in-throws-after';
		const snapshots = browserSnapshots();
		const original = snapshots.pendingServerLogouts.bind(snapshots);
		const spy = vi
			.spyOn(snapshots, 'pendingServerLogouts')
			.mockImplementationOnce(original)
			.mockRejectedValueOnce(new Error('broken'));
		const api = fakeApi();
		expect(await standaloneLogin(slug, 'password', api as never)).toMatchObject({
			ok: false,
			code: 'session_transition_unavailable'
		});
		expect(api.logout).toHaveBeenCalledWith(slug);
		expect((await snapshots.generation(identityOf(slug))).ok).toBe(false);
		spy.mockRestore();
		vi.unstubAllGlobals();
	});

	it('reports logout_pending and does not post when the pending server sign-out fails', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-in-pending-fails';
		await browserSnapshots().localSignOut(identityOf(slug));
		const api = fakeApi();
		api.logout.mockRejectedValue(new NetworkError());
		expect(await standaloneLogin(slug, 'password', api as never)).toMatchObject({
			ok: false,
			code: 'logout_pending'
		});
		expect(api.login).not.toHaveBeenCalled();
		vi.unstubAllGlobals();
	});

	it('restores the sign-out and stops when the room is still signed out after clearing', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-in-still-signed-out';
		const snapshots = browserSnapshots();
		await snapshots.localSignOut(identityOf(slug));
		const clear = vi
			.spyOn(snapshots, 'clearSignOutAfterSignIn')
			.mockResolvedValueOnce({ ok: true, value: undefined });
		const restore = vi.spyOn(snapshots, 'localSignOut');
		const api = fakeApi();
		expect(await standaloneLogin(slug, 'password', api as never)).toMatchObject({
			ok: false,
			code: 'signed_out'
		});
		expect(api.login).not.toHaveBeenCalled();
		expect(restore).toHaveBeenCalledWith(identityOf(slug));
		clear.mockRestore();
		restore.mockRestore();
		vi.unstubAllGlobals();
	});
});

describe('standalone sign-out paths', () => {
	it('completes sign-out: local marker, server sign-out, then no pending marker', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-out-complete';
		const snapshots = browserSnapshots();
		const api = fakeApi();
		expect(await standaloneLogout(slug, api as never)).toEqual({ ok: true, result: {} });
		expect(api.logout).toHaveBeenCalledWith(slug);
		const pending = await snapshots.pendingServerLogouts();
		expect(pending.ok && pending.value.some((identity) => identity.slug === slug)).toBe(false);
		expect((await snapshots.generation(identityOf(slug))).ok).toBe(false);
		vi.unstubAllGlobals();
	});

	it('does not post when the local marker cannot be stored', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const snapshots = browserSnapshots();
		const spy = vi
			.spyOn(snapshots, 'localSignOut')
			.mockResolvedValueOnce({ ok: false, reason: 'unavailable' });
		const api = fakeApi();
		expect(await standaloneLogout('standalone-out-unmarked', api as never)).toMatchObject({
			ok: false,
			code: 'local_clear_unconfirmed'
		});
		expect(api.logout).not.toHaveBeenCalled();
		spy.mockRestore();
		vi.unstubAllGlobals();
	});

	it('keeps the server sign-out pending when the request fails', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const slug = 'standalone-out-request-fails';
		const snapshots = browserSnapshots();
		const api = fakeApi();
		api.logout.mockRejectedValueOnce(new NetworkError());
		expect(await standaloneLogout(slug, api as never)).toMatchObject({
			ok: false,
			code: 'server_logout_pending'
		});
		const pending = await snapshots.pendingServerLogouts();
		expect(pending.ok && pending.value.some((identity) => identity.slug === slug)).toBe(true);
		vi.unstubAllGlobals();
	});

	it('reports a server sign-out whose marker cannot be acknowledged', async () => {
		vi.stubGlobal('indexedDB', new IDBFactory());
		vi.stubGlobal('navigator', { locks: serialLocks() });
		const snapshots = browserSnapshots();
		const spy = vi
			.spyOn(snapshots, 'acknowledgeServerLogout')
			.mockResolvedValueOnce({ ok: false, reason: 'unavailable' });
		const api = fakeApi();
		expect(await standaloneLogout('standalone-out-ack', api as never)).toMatchObject({
			ok: false,
			code: 'logout_marker_unacknowledged'
		});
		expect(api.logout).toHaveBeenCalledTimes(1);
		spy.mockRestore();
		vi.unstubAllGlobals();
	});
});

describe('reconnect write gate', () => {
	it('treats offline/online signals as hints and waits for successful access plus feed', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const connectivity = fakeConnectivity();
		const room = handle(api, storage, { connectivity: connectivity.target });
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));

		api.whoAmI.mockRejectedValueOnce(new NetworkError());
		connectivity.emit('offline');
		expect(room.store.canWrite).toBe(false);
		// The offline signal itself runs the check, which fails.
		await vi.waitFor(() => expect(api.whoAmI).toHaveBeenCalledTimes(2));
		await settle();
		expect(room.store.canWrite).toBe(false);
		expect(api.changes).toHaveBeenCalledTimes(1);

		// An online signal is only a hint: a failing check keeps writes blocked.
		api.whoAmI.mockRejectedValueOnce(new NetworkError());
		connectivity.emit('online');
		await vi.waitFor(() => expect(api.whoAmI).toHaveBeenCalledTimes(3));
		await settle();
		expect(room.store.canWrite).toBe(false);

		connectivity.emit('online');
		await vi.waitFor(() => expect(api.changes).toHaveBeenCalledTimes(2));
		expect(room.store.canWrite).toBe(true);
		room.release();
		storage.close();
	});

	it('keeps writes blocked until both access and the changes feed refresh', async () => {
		FakeEventSource.reset();
		const storage = snapshots();
		const api = fakeApi();
		const room = handle(api, storage);
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		const stream = FakeEventSource.last;
		stream.open();

		api.whoAmI.mockRejectedValueOnce(new NetworkError());
		stream.fail(true);
		expect(room.store.canWrite).toBe(false);
		stream.open();
		await vi.waitFor(() => expect(api.whoAmI).toHaveBeenCalledTimes(2));
		await settle();
		expect(room.store.canWrite).toBe(false);
		expect(api.changes).toHaveBeenCalledTimes(1);

		stream.fail(true);
		stream.open();
		await vi.waitFor(() => expect(api.changes).toHaveBeenCalledTimes(2));
		expect(room.store.canWrite).toBe(true);
		room.release();
		storage.close();
	});
});

describe('share snapshot privacy', () => {
	it('strips member-room metadata from saved and hydrated share views', async () => {
		const storage = snapshots();
		const token = 's'.repeat(43);
		const sharedList = makeList({ uid: 'public-list', slug: '' });
		const sharedItem = makeItem(sharedList.uid, { uid: 'public-item' });
		const memberFeed = makeFeed({
			seq: 8,
			full: true,
			room: ROOM,
			lists: [sharedList],
			items: [sharedItem]
		});
		const shareSend = vi.fn(async (): Promise<OpResponse> => ({
			op_id: 'unused',
			status: 'applied',
			result: {},
			seq: 8
		}));
		const shareUrl = (value: string) => `/api/v1/share/${value}/events`;
		const reset = vi.fn(async () => ({ token: 'replacement' }));
		const onlineApi = new ShareApi({
			shareChanges: vi.fn(async () => memberFeed),
			sendShareOp: shareSend,
			shareEventsUrl: shareUrl,
			resetShareLink: reset
		});
		const online = new RoomHandle(token, {
			api: onlineApi,
			snapshotStore: storage,
			sessionLocks: null,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		online.retain();
		await vi.waitFor(() => expect(online.store.canWrite).toBe(true));
		expect(online.store.room).toEqual(ROOM);
		const saved = await storage.read({ kind: 'share', token });
		expect(saved).toMatchObject({ ok: true, value: { room: null, lists: [sharedList] } });
		online.release();

		const offlineChanges = vi.fn(async () => {
			throw new NetworkError();
		});
		const offlineApi = new ShareApi({
			shareChanges: offlineChanges,
			sendShareOp: shareSend,
			shareEventsUrl: shareUrl,
			resetShareLink: reset
		});
		const offline = new RoomHandle(token, {
			api: offlineApi,
			snapshotStore: storage,
			sessionLocks: null,
			hydrateSavedView: true,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		offline.retain();
		await vi.waitFor(() => expect(offlineChanges).toHaveBeenCalledTimes(1));
		await settle();
		expect(offline.store.lists).toEqual([sharedList]);
		expect(offline.store.itemsOf(sharedList.uid)).toEqual([sharedItem]);
		expect(offline.store.room).toBeNull();
		expect(offline.store.canWrite).toBe(false);
		offline.release();
		storage.close();
	});
});

describe('room membership versus share access', () => {
	it('does not reapply a pre-reset feed with stale room membership', async () => {
		const storage = snapshots();
		const token = 'r'.repeat(43);
		const sharedList = makeList({ uid: 'member-list', slug: '' });
		const memberFeed = makeFeed({ seq: 8, full: true, room: ROOM, lists: [sharedList] });
		const oldFeed = deferred<Feed>();
		const changes = vi
			.fn()
			.mockResolvedValueOnce(memberFeed)
			.mockReturnValueOnce(oldFeed.promise)
			.mockResolvedValue(makeFeed({ seq: 9, full: true, room: null, lists: [sharedList] }));
		const api = new ShareApi({
			shareChanges: changes,
			sendShareOp: vi.fn(),
			shareEventsUrl: (value) => `/api/v1/share/${value}/events`,
			resetShareLink: vi.fn(async () => {
				throw new ApiError(401, 'not_authenticated', 'Sign in to this room.');
			})
		});
		const share = new RoomHandle(token, {
			api,
			snapshotStore: storage,
			sessionLocks: null,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		share.retain();
		await vi.waitFor(() => expect(share.store.canWrite).toBe(true));
		const refreshing = share.store.refresh();
		await vi.waitFor(() => expect(changes).toHaveBeenCalledTimes(2));
		expect(await share.resetShareLink(sharedList)).toMatchObject({
			ok: false,
			code: 'not_authenticated'
		});
		oldFeed.resolve({ ...memberFeed, seq: 9 });
		expect(await refreshing).toBe(false);
		await vi.waitFor(() => expect(share.store.canWrite).toBe(true));
		expect(share.store.room).toBeNull();
		expect(await storage.read({ kind: 'share', token })).toMatchObject({
			ok: true,
			value: { room: null, seq: 9 }
		});
		share.release();
		storage.close();
	});
	it('settles an in-flight share edit after member reset 401 and refreshes without member privileges', async () => {
		const storage = snapshots();
		const token = 'q'.repeat(43);
		const sharedList = makeList({ uid: 'share-list', slug: '' });
		const sharedItem = makeItem(sharedList.uid, { uid: 'share-item' });
		const memberFeed = makeFeed({
			seq: 8,
			full: true,
			room: ROOM,
			lists: [sharedList],
			items: [sharedItem]
		});
		const publicFeed = makeFeed({
			seq: 9,
			full: true,
			room: null,
			lists: [sharedList],
			items: [{ ...sharedItem, done: true, changed_seq: 9, completed_at: '2026-10-06T18:00:00Z' }]
		});
		const changes = vi.fn().mockResolvedValueOnce(memberFeed).mockResolvedValue(publicFeed);
		const answer = deferred<OpResponse>();
		const sendShareOp = vi.fn(async (_token: string, op: SentOp) =>
			sendShareOp.mock.calls.length === 1 ? answer.promise : applied(op, 9)
		);
		const reset = vi.fn(async () => {
			throw new ApiError(401, 'not_authenticated', 'Sign in to this room.');
		});
		const api = new ShareApi({
			shareChanges: changes,
			sendShareOp,
			shareEventsUrl: (value) => `/api/v1/share/${value}/events`,
			resetShareLink: reset
		});
		const share = new RoomHandle(token, {
			api,
			snapshotStore: storage,
			sessionLocks: null,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		share.retain();
		await vi.waitFor(() => expect(share.store.canWrite).toBe(true));
		const action = share.setDone(sharedItem, true);
		await vi.waitFor(() => expect(sendShareOp).toHaveBeenCalledTimes(1));
		expect(share.store.queued).toBe(1);
		expect(await share.resetShareLink(sharedList)).toMatchObject({
			ok: false,
			code: 'not_authenticated'
		});
		expect(share.store.room).toBeNull();
		expect(share.store.lists).toEqual([sharedList]);
		await settle(); // revalidation now waits on the share op's held refresh
		expect(changes).toHaveBeenCalledTimes(1);
		expect(share.store.canWrite).toBe(false);
		answer.resolve(applied(sendShareOp.mock.calls[0][1], 9));
		expect(await action).toMatchObject({ ok: true });
		await vi.waitFor(() => expect(share.store.canWrite).toBe(true));
		expect(share.store.queued).toBe(0);
		expect(share.store.pendingOps).toEqual([]);
		expect(share.store.room).toBeNull();
		expect(await storage.read({ kind: 'share', token })).toMatchObject({
			ok: true,
			value: { room: null, seq: 9 }
		});
		expect(await share.addListTag(sharedList, 'fresh')).toMatchObject({ ok: true });
		expect(sendShareOp).toHaveBeenCalledTimes(2);
		share.release();
		storage.close();
	});
	it('keeps the public view after room reset returns 401 not_authenticated', async () => {
		const storage = snapshots();
		const token = 'p'.repeat(43);
		const sharedList = makeList({ uid: 'public-list', slug: '' });
		const memberFeed = makeFeed({ seq: 8, full: true, room: ROOM, lists: [sharedList] });
		const publicFeed = { ...memberFeed, room: null };
		const changes = vi.fn().mockResolvedValueOnce(memberFeed).mockResolvedValue(publicFeed);
		const reset = vi.fn(async () => {
			throw new ApiError(401, 'not_authenticated', 'Sign in to this room.');
		});
		const api = new ShareApi({
			shareChanges: changes,
			sendShareOp: vi.fn(),
			shareEventsUrl: (value) => `/api/v1/share/${value}/events`,
			resetShareLink: reset
		});
		const share = new RoomHandle(token, {
			api,
			snapshotStore: storage,
			sessionLocks: null,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		share.retain();
		await vi.waitFor(() => expect(share.store.canWrite).toBe(true));
		expect(share.store.room).toEqual(ROOM);
		expect(await share.resetShareLink(sharedList)).toMatchObject({
			ok: false,
			code: 'not_authenticated'
		});
		expect(share.store.room).toBeNull();
		expect(share.store.lists).toEqual([sharedList]);
		await vi.waitFor(() => expect(changes.mock.calls.length).toBeGreaterThan(1));
		await vi.waitFor(() => expect(share.store.canWrite).toBe(true));
		expect(await storage.read({ kind: 'share', token })).toMatchObject({
			ok: true,
			value: { room: null, lists: [sharedList] }
		});
		expect(await storage.read({ kind: 'room', slug: ROOM.slug })).toMatchObject({
			ok: true,
			value: null
		});
		expect(await share.resetShareLink(sharedList)).toMatchObject({
			ok: false,
			code: 'invalid_request'
		});
		expect(reset).toHaveBeenCalledTimes(1);
		share.release();
		storage.close();
	});
});

describe('cross-handle revocation', () => {
	it('immediately clears another open room handle when access is confirmed revoked', async () => {
		const storage = sharedMemorySnapshots();
		const firstApi = fakeApi();
		const first = handle(firstApi, storage);
		await vi.waitFor(() => expect(first.store.canWrite).toBe(true));
		const secondApi = fakeApi();
		const second = handle(secondApi, storage);
		await vi.waitFor(() => expect(second.store.canWrite).toBe(true));
		secondApi.sendOp.mockRejectedValueOnce(
			new ApiError(401, 'not_authenticated', 'Sign in to this room.')
		);
		const result = second.addListTag(list, 'denied');
		let settled = false;
		void result.then(() => (settled = true));
		await vi.waitFor(() => expect(secondApi.sendOp).toHaveBeenCalledTimes(1));
		await settle();
		expect(first.store.lists).toEqual([]);
		expect(second.store.lists).toEqual([]);
		expect(first.store.canWrite).toBe(false);
		expect(second.store.canWrite).toBe(false);
		expect(settled).toBe(false);
		first.release();
		second.release();
		storage.close();
	});
});

describe('unavailable snapshot state', () => {
	it('keeps authorized online writes working but blocks sign-in when pending sign-out state is unreadable', async () => {
		const storage = {
			generation: vi.fn(async () => ({ ok: false as const, reason: 'unavailable' as const })),
			pendingServerLogouts: vi.fn(async () => ({
				ok: false as const,
				reason: 'unavailable' as const
			})),
			prune: vi.fn(async () => ({ ok: true as const, value: 0 })),
			onClear: vi.fn(() => () => {})
		} as unknown as SnapshotStore;
		const api = fakeApi();
		const room = new RoomHandle(ROOM.slug, {
			api,
			snapshotStore: storage,
			sessionLocks: null,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		room.retain();
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		const write = room.addListTag(list, 'online');
		await vi.waitFor(() => expect(api.sendOp).toHaveBeenCalledTimes(1));
		await write;
		expect(room.store.canWrite).toBe(true);
		expect(room.store.snapshotWarning).toBeTruthy();

		const signin = await room.login('secret');
		expect(signin).toMatchObject({ ok: false, code: 'session_transition_unavailable' });
		expect(api.login).not.toHaveBeenCalled();
		room.release();
	});
});

describe('room session transition serialization', () => {
	it('holds sign-in until the old logout answer is settled and access is refreshed', async () => {
		const storage = snapshots();
		const locks = serialLocks();
		let finishLogout!: () => void;
		const logoutWait = new Promise<void>((resolve) => (finishLogout = resolve));
		let logoutStarted!: () => void;
		const logoutEntered = new Promise<void>((resolve) => (logoutStarted = resolve));
		const firstApi = fakeApi();
		firstApi.logout.mockImplementation(async () => {
			logoutStarted();
			await logoutWait;
		});
		const first = new RoomHandle(ROOM.slug, {
			api: firstApi,
			snapshotStore: storage,
			sessionLocks: locks,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		first.retain();
		await settle();

		const logout = first.logout();
		await logoutEntered;
		const secondApi = fakeApi();
		const second = new RoomHandle(ROOM.slug, {
			api: secondApi,
			snapshotStore: storage,
			sessionLocks: locks,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		const signingIn = second.login('secret');
		await settle();
		expect(secondApi.login).not.toHaveBeenCalled();
		finishLogout();
		expect(await logout).toEqual({ ok: true, result: {} });
		expect(await signingIn).toEqual({ ok: true, result: ROOM });
		expect(secondApi.login).toHaveBeenCalledTimes(1);
		expect(secondApi.whoAmI).toHaveBeenCalledTimes(1);
		expect(secondApi.changes).toHaveBeenCalledTimes(1);
		expect(second.store.canWrite).toBe(true);
		first.release();
		second.release();
		storage.close();
	});

	it('does not enable writes if a newer local sign-out happens during sign-in', async () => {
		const storage = snapshots();
		const locks = serialLocks();
		const api = fakeApi();
		let resolveLogin!: (value: typeof ROOM) => void;
		api.login.mockReturnValue(new Promise((resolve) => (resolveLogin = resolve)));
		const room = new RoomHandle(ROOM.slug, {
			api,
			snapshotStore: storage,
			sessionLocks: locks,
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		const signingIn = room.login('secret');
		await settle();
		const logout = room.logout();
		await settle();
		resolveLogin(ROOM);
		expect(await signingIn).toMatchObject({ ok: false, code: 'signed_out' });
		expect(await logout).toEqual({ ok: true, result: {} });
		expect(room.store.canWrite).toBe(false);
		expect(api.whoAmI).not.toHaveBeenCalled();
		expect(api.changes).not.toHaveBeenCalled();
		room.release();
		storage.close();
	});

	it('retries a delayed pre-sign-out operation with its original op_id after revalidation', async () => {
		FakeEventSource.reset();
		const storage = snapshots();
		const api = fakeApi();
		const firstAnswer = deferred<OpResponse>();
		const retryAnswer = deferred<OpResponse>();
		const sends: SentOp[] = [];
		api.sendOp.mockImplementation(async (_slug, op) => {
			sends.push(op);
			return sends.length === 1 ? firstAnswer.promise : retryAnswer.promise;
		});
		const room = new RoomHandle(ROOM.slug, {
			api,
			snapshotStore: storage,
			sessionLocks: serialLocks(),
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		room.retain();
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
		const action = room.addListTag(list, 'Shared');
		await vi.waitFor(() => expect(sends).toHaveLength(1));
		const opId = sends[0].op_id;

		expect(await room.logout()).toEqual({ ok: true, result: {} });
		expect(room.queuedOps[0].op_id).toBe(opId);
		expect(FakeEventSource.instances[0].closed).toBe(true);
		expect(await room.login('secret')).toEqual({ ok: true, result: ROOM });
		expect(room.store.canWrite).toBe(true);
		await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));

		firstAnswer.reject(new ApiError(401, 'not_authenticated', 'Sign in to this room.'));
		await vi.waitFor(() => expect(sends).toHaveLength(2));
		expect(sends[1]).toEqual(sends[0]);
		expect(room.store.queued).toBe(1);
		// The waiting change is shown again once access is confirmed.
		expect(room.store.pendingOps.map((pending) => pending.op.op_id)).toEqual([opId]);
		retryAnswer.resolve(applied(sends[1], 6));
		await action;
		expect(room.store.queued).toBe(0);
		expect(room.store.canWrite).toBe(true);
		room.release();
		storage.close();
	});
});

describe('offline editing (6.2d)', () => {
	/** A server that answers what the device sends, with the rows it changed. */
	function answering(api: ReturnType<typeof fakeApi>, sent: SentOp[]) {
		api.sendOp.mockImplementation(async (_slug, op) => {
			sent.push(op);
			const result =
				op.type === 'item.add'
					? { item_uid: op.uid, outcome: 'added', changed_seq: 3 }
					: { changed_seq: 2 };
			return { op_id: op.op_id, status: 'applied', result, seq: 7 };
		});
	}

	it('keeps offline edits across a reload, shows them, and sends them in order when back online', async () => {
		const storage = snapshots();
		const queue = new MemoryQueueStorage();
		const online = fakeApi();
		const first = handle(online, storage);
		await vi.waitFor(() => expect(first.store.canWrite).toBe(true));
		first.release();

		const connectivity = fakeConnectivity();
		const offlineApi = fakeApi();
		offlineApi.whoAmI.mockRejectedValue(new NetworkError());
		offlineApi.changes.mockRejectedValue(new NetworkError());
		const offline = handle(offlineApi, storage, {
			hydrateSavedView: true,
			queueStorage: queue,
			connectivity: connectivity.target
		});
		await vi.waitFor(() => expect(offlineApi.whoAmI).toHaveBeenCalledTimes(1));
		await settle();
		expect(offline.store.canEdit).toBe(true);
		expect(offline.store.canWrite).toBe(false);

		void offline.setDone(item, true);
		void offline.editItem(item, { name: 'milk', description: 'cold' });
		void offline.addItem(list, 'bread');
		expect(offlineApi.sendOp).not.toHaveBeenCalled();
		// The three ops are written to storage before the page is closed.
		await vi.waitFor(async () => expect(await queue.read()).toHaveLength(3));
		offline.release();

		// A reload while still offline: the stored ops are projected at once.
		const reloaded = handle(offlineApi, storage, { hydrateSavedView: true, queueStorage: queue });
		await vi.waitFor(() => expect(reloaded.store.itemsOf(list.uid)).toHaveLength(2));
		expect(reloaded.queuedOps.map((sent) => sent.type)).toEqual([
			'item.set_done',
			'item.edit',
			'item.add'
		]);
		expect(reloaded.store.item(item.uid)).toMatchObject({ done: true, description: 'cold' });
		expect(reloaded.waitingCount).toBe(3);

		// Back online: the 'online' signal revalidates, and the queue goes out in order.
		const sent: SentOp[] = [];
		answering(offlineApi, sent);
		offlineApi.whoAmI.mockResolvedValue(ROOM);
		offlineApi.changes.mockResolvedValue(
			makeFeed({
				seq: 7,
				full: true,
				lists: [list],
				items: [{ ...item, done: true, changed_seq: 2 }]
			})
		);
		connectivity.emit('online');
		await vi.waitFor(() => expect(offlineApi.sendOp).toHaveBeenCalledTimes(3));
		expect(sent.map((op) => op.type)).toEqual(['item.set_done', 'item.edit', 'item.add']);
		expect(sent[0]).toMatchObject({ item_uid: item.uid, done: true, base_seq: 1 });
		// The edit was based on the same view: its base moved to the seq the tick got.
		expect(sent[1]).toMatchObject({ base_seq: 2, name: 'milk', description: 'cold' });
		await vi.waitFor(() => expect(reloaded.waitingCount).toBe(0));
		expect(reloaded.queuedOps).toEqual([]);
		reloaded.release();
		storage.close();
	});

	it('moves later ops on a new item to the existing item when the add is a duplicate', async () => {
		const storage = snapshots();
		const queue = new MemoryQueueStorage();
		const online = fakeApi();
		const first = handle(online, storage);
		await vi.waitFor(() => expect(first.store.canWrite).toBe(true));
		first.release();

		const connectivity = fakeConnectivity();
		const offlineApi = fakeApi();
		offlineApi.whoAmI.mockRejectedValue(new NetworkError());
		offlineApi.changes.mockRejectedValue(new NetworkError());
		const offline = handle(offlineApi, storage, {
			hydrateSavedView: true,
			queueStorage: queue,
			connectivity: connectivity.target
		});
		await vi.waitFor(() => expect(offlineApi.whoAmI).toHaveBeenCalledTimes(1));
		await settle();

		const added = await offline.addItem(list, 'eggs');
		expect(added).toMatchObject({ ok: true, result: { outcome: 'added' } });
		const addOp = offline.queuedOps[0];
		if (addOp.type !== 'item.add' || addOp.uid === undefined) throw new Error('no add queued');
		const eggsUid = addOp.uid;
		void offline.setDone({ uid: eggsUid, list_uid: list.uid, changed_seq: 0 }, true);
		expect(offline.store.itemsOf(list.uid).map((row) => row.name)).toContain('eggs');
		offline.release();

		// The server already had "eggs" on the list: its add is a duplicate.
		const sent: SentOp[] = [];
		offlineApi.sendOp.mockImplementation(async (_slug, op) => {
			sent.push(op);
			if (op.type === 'item.add') {
				return {
					op_id: op.op_id,
					status: 'rejected',
					code: 'duplicate_active',
					message: "'eggs' is already on the list",
					item_uid: 'kept-eggs',
					seq: 8
				};
			}
			return { op_id: op.op_id, status: 'applied', result: {}, seq: 8 };
		});
		offlineApi.whoAmI.mockResolvedValue(ROOM);
		offlineApi.changes.mockResolvedValue(
			makeFeed({ seq: 8, full: true, lists: [list], items: [item] })
		);
		const back = handle(offlineApi, storage, {
			hydrateSavedView: true,
			queueStorage: queue,
			connectivity: connectivity.target
		});
		await vi.waitFor(() => expect(offlineApi.sendOp).toHaveBeenCalledTimes(2));
		expect(sent[1]).toMatchObject({ type: 'item.set_done', item_uid: 'kept-eggs', done: true });
		// The waited add is not an error (R6): no toast and no Not saved entry.
		await settle();
		expect(back.store.notice).toBeNull();
		expect(back.store.notSaved).toEqual([]);
		back.release();
		storage.close();
	});

	it('bases a change on the seq its own answer just gave the row, before the feed shows it', async () => {
		const storage = snapshots();
		const api = fakeApi();
		const sent: SentOp[] = [];
		const answers: Deferred<OpResponse>[] = [];
		api.sendOp.mockImplementation(async (_slug, op) => {
			sent.push(op);
			const answer = deferred<OpResponse>();
			answers.push(answer);
			return answer.promise;
		});
		const room = handle(api, storage);
		await vi.waitFor(() => expect(room.store.canWrite).toBe(true));
		// From now on the feed does not answer: the device only has its own answers.
		api.changes.mockImplementation(() => new Promise<Feed>(() => undefined));

		void room.toggleItemTag(item, 'Market');
		await vi.waitFor(() => expect(sent).toHaveLength(1));
		answers[0].resolve({
			op_id: sent[0].op_id,
			status: 'applied',
			result: { changed_seq: 2 },
			seq: 6
		});
		await vi.waitFor(() => expect(room.store.item(item.uid)?.changed_seq).toBe(2));

		const row = room.store.item(item.uid);
		if (!row) throw new Error('the item is not shown');
		void room.setDone(row, true);
		await vi.waitFor(() => expect(sent).toHaveLength(2));
		expect(sent[1]).toMatchObject({ type: 'item.set_done', base_seq: 2 });
		room.release();
		storage.close();
	});
});

describe('not-saved changes (6.3)', () => {
	/** A device that saved the list online, then goes offline with its own queue. */
	async function offlineDevice(queue: QueueStorage = new MemoryQueueStorage()) {
		const storage = snapshots();
		const online = fakeApi();
		const first = handle(online, storage);
		await vi.waitFor(() => expect(first.store.canWrite).toBe(true));
		first.release();
		const connectivity = fakeConnectivity();
		const offlineApi = fakeApi();
		offlineApi.whoAmI.mockRejectedValue(new NetworkError());
		offlineApi.changes.mockRejectedValue(new NetworkError());
		const offline = handle(offlineApi, storage, {
			hydrateSavedView: true,
			queueStorage: queue,
			connectivity: connectivity.target
		});
		await vi.waitFor(() => expect(offlineApi.whoAmI).toHaveBeenCalledTimes(1));
		await settle();
		return { storage, offline, offlineApi, connectivity };
	}

	/** Back online: the server answers `answer` for each op, and the feed says `items`. */
	function reconnect(
		device: Awaited<ReturnType<typeof offlineDevice>>,
		answer: (op: SentOp) => OpResponse,
		items: Item[] = [{ ...item, done: false, changed_seq: 6 }]
	) {
		const { offlineApi, connectivity } = device;
		offlineApi.sendOp.mockImplementation(async (_slug, op) => answer(op));
		offlineApi.whoAmI.mockResolvedValue(ROOM);
		offlineApi.changes.mockResolvedValue(makeFeed({ seq: 8, full: true, lists: [list], items }));
		connectivity.emit('online');
	}

	it('puts a change refused after it waited on the Not saved list, not in a toast', async () => {
		const device = await offlineDevice();
		const { offline } = device;
		void offline.setDone(item, true);
		reconnect(device, (op) => ({
			op_id: op.op_id,
			status: 'rejected',
			code: 'changed_meanwhile',
			message: 'Someone else changed this meanwhile.',
			seq: 8
		}));

		await vi.waitFor(() => expect(offline.store.notSaved).toHaveLength(1));
		expect(offline.store.notSaved[0]).toMatchObject({
			code: 'changed_meanwhile',
			text: "Tick 'milk': someone else changed it meanwhile."
		});
		expect(offline.store.notice).toBeNull();
		expect(offline.store.item(item.uid)?.done).toBe(false);
		offline.release();
		device.storage.close();
	});

	it("sends a refused change again as a new op, based on the row's current changed_seq", async () => {
		const device = await offlineDevice();
		const { offline } = device;
		void offline.setDone(item, true);
		const first: SentOp[] = [];
		reconnect(device, (op) => {
			first.push(op);
			return {
				op_id: op.op_id,
				status: 'rejected',
				code: 'changed_meanwhile',
				message: '',
				seq: 8
			};
		});
		await vi.waitFor(() => expect(offline.store.notSaved).toHaveLength(1));
		await vi.waitFor(() => expect(offline.store.canWrite).toBe(true));

		// Someone changed the row again: the device now knows changed_seq 9.
		const again: SentOp[] = [];
		device.offlineApi.sendOp.mockImplementation(async (_slug, op) => {
			again.push(op);
			return { op_id: op.op_id, status: 'applied', result: { changed_seq: 10 }, seq: 9 };
		});
		device.offlineApi.changes.mockResolvedValue(
			makeFeed({
				seq: 9,
				full: true,
				lists: [list],
				items: [{ ...item, done: false, changed_seq: 9 }]
			})
		);
		await offline.store.refresh();

		const result = await offline.saveMineAnyway(offline.store.notSaved[0].id);
		expect(result.ok).toBe(true);
		expect(offline.store.notSaved).toEqual([]);
		expect(again).toHaveLength(1);
		expect(again[0]).toMatchObject({
			type: 'item.set_done',
			item_uid: item.uid,
			done: true,
			base_seq: 9
		});
		expect(again[0].op_id).not.toBe(first[0].op_id);
		offline.release();
		device.storage.close();
	});

	it('shows a loaded op that may already have been sent once, as uncertain', async () => {
		const storage = snapshots();
		const online = fakeApi();
		const first = handle(online, storage);
		await vi.waitFor(() => expect(first.store.canWrite).toBe(true));
		first.release();
		const queue = new MemoryQueueStorage();
		const sent: SentOp = {
			op_id: 'maybe-sent',
			type: 'item.quantity_delta',
			list_uid: list.uid,
			item_uid: item.uid,
			delta: 1
		};
		await queue.add({ ...newStoredEntry(sent, '2026-10-06T17:00:00.000Z'), sent: true });
		const connectivity = fakeConnectivity();
		const offlineApi = fakeApi();
		offlineApi.whoAmI.mockRejectedValue(new NetworkError());
		offlineApi.changes.mockRejectedValue(new NetworkError());
		const offline = handle(offlineApi, storage, {
			hydrateSavedView: true,
			queueStorage: queue,
			connectivity: connectivity.target
		});
		await vi.waitFor(() => expect(offline.waitingCount).toBe(1));
		await settle();
		// The server may already have the +1: the saved quantity is shown, not one more.
		expect(offline.store.item(item.uid)?.quantity).toBe(item.quantity);
		expect(offline.store.pendingOps[0]).toMatchObject({ uncertain: true });
		offline.release();
		storage.close();
	});
});
