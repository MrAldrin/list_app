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
import { FakeEventSource, makeFeed, makeItem, makeList, ROOM, settle } from './test-helpers';
import { ApiError, NetworkError } from './types';
import type { Feed, OpResponse, SentOp } from './types';
import { createSnapshotStore, type SnapshotStore } from './snapshot-store';
import type { SessionLockManager } from './session-transition';

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
	} = {}
) {
	const room = new RoomHandle(ROOM.slug, {
		api,
		snapshotStore: storage,
		sessionLocks: extra.sessionLocks === undefined ? serialLocks() : extra.sessionLocks,
		hydrateSavedView: extra.hydrateSavedView,
		createEventSource: (url) => new FakeEventSource(url),
		visibility: null,
		online: extra.connectivity ?? null
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

		const results = await Promise.all([
			offline.renameRoom('new'),
			offline.createList('new'),
			offline.renameList(list, 'new'),
			offline.deleteList(list),
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
			offline.changePassword('old', 'new'),
			offline.deleteRoom('password'),
			offline.resetShareLink(list)
		]);
		expect(results.every((result) => !result.ok && result.code === 'read_only')).toBe(true);
		expect(offlineApi.sendOp).not.toHaveBeenCalled();
		expect(offlineApi.changePassword).not.toHaveBeenCalled();
		expect(offlineApi.deleteRoom).not.toHaveBeenCalled();
		expect(offlineApi.resetShareLink).not.toHaveBeenCalled();
		expect(offline.queuedOps).toEqual([]);
		expect(offline.store.item(item.uid)).toEqual(item);
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
		connectivity.emit('online');
		expect(room.store.canWrite).toBe(false);
		await vi.waitFor(() => expect(api.whoAmI).toHaveBeenCalledTimes(2));
		await settle();
		expect(room.store.canWrite).toBe(false);
		expect(api.changes).toHaveBeenCalledTimes(1);

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
		expect(room.store.pendingOps).toEqual([]);
		retryAnswer.resolve(applied(sends[1], 6));
		await action;
		expect(room.store.queued).toBe(0);
		expect(room.store.canWrite).toBe(true);
		room.release();
		storage.close();
	});
});
