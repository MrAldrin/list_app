// @vitest-environment happy-dom
// The browser can show the password prompt as soon as the initial 401 arrives,
// while its IndexedDB clear is still pending.

import { IDBFactory } from 'fake-indexeddb';
import { createRawSnippet, flushSync, mount, unmount } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import PageShell from '#lib/room/PageShell.svelte';
import { deferred, fakeRoomApi, FakeEventSource, makeFeed, ROOM, waitFor } from './test-helpers';
import { RoomHandle } from './index';
import { ApiError } from './types';
import { createSnapshotStore, type SnapshotStore } from './snapshot-store';
import type { SessionLockManager } from './session-transition';
import type { Room } from './types';

const INTERRUPTED = 'Room sign-in was interrupted by sign-out.';

function immediateSessionLocks(): SessionLockManager {
	return {
		request: async <T>(_name: string, _options: LockOptions, callback: () => Promise<T>) =>
			callback()
	} as SessionLockManager;
}

function renderRoomPage(room: RoomHandle) {
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(PageShell, {
		target,
		props: {
			open: () => {
				room.retain();
				return room;
			},
			close: (opened: RoomHandle) => opened.release(),
			canSignIn: true,
			connectTitle: 'Connect to load this room.',
			failedTitle: 'Could not load this room.',
			content: createRawSnippet<[RoomHandle]>(() => ({ render: () => '<p>Room contents</p>' }))
		}
	});
	flushSync();
	return { target, component };
}

describe('initial room sign-in race', () => {
	it.each(['precheck', 'login request'] as const)(
		'allows a password submitted from the initial 401 prompt when its clear hint arrives during %s',
		async (stage) => {
			const snapshots = createSnapshotStore({
				indexedDB: new IDBFactory(),
				databaseName: 'index-signin-race',
				channel: null
			});
			const api = fakeRoomApi({
				changes: vi.fn(async (_slug: string, since: number) => makeFeed({ seq: since, full: true }))
			});
			api.whoAmI.mockRejectedValueOnce(
				new ApiError(401, 'not_authenticated', 'Sign in to this room.')
			);

			const loginStarted = deferred<void>();
			const allowLogin = deferred<Room>();
			if (stage === 'login request') {
				api.login.mockImplementationOnce(async () => {
					loginStarted.resolve();
					return allowLogin.promise;
				});
			}

			const clearStarted = deferred<void>();
			const allowClear = deferred<void>();
			const originalClear = snapshots.clear.bind(snapshots);
			vi.spyOn(snapshots, 'clear').mockImplementation(async (...args) => {
				clearStarted.resolve();
				await allowClear.promise;
				return originalClear(...args);
			});

			const hintStarted = deferred<void>();
			const allowHint = deferred<void>();
			const hintDelivered = deferred<void>();
			const originalOnClear = snapshots.onClear.bind(snapshots);
			vi.spyOn(snapshots, 'onClear').mockImplementation((listener) =>
				originalOnClear((hint) => {
					hintStarted.resolve();
					void allowHint.promise.then(() => {
						listener(hint);
						hintDelivered.resolve();
					});
				})
			);

			const signInCheckStarted = deferred<void>();
			const allowSignInCheck =
				deferred<Awaited<ReturnType<SnapshotStore['pendingServerLogouts']>>>();
			const originalPendingLogouts = snapshots.pendingServerLogouts.bind(snapshots);
			let pendingLogoutChecks = 0;
			vi.spyOn(snapshots, 'pendingServerLogouts').mockImplementation(async () => {
				pendingLogoutChecks += 1;
				if (stage === 'precheck' && pendingLogoutChecks === 1) {
					signInCheckStarted.resolve();
					return allowSignInCheck.promise;
				}
				return originalPendingLogouts();
			});

			FakeEventSource.reset();
			const room = new RoomHandle(ROOM.slug, {
				api,
				snapshotStore: snapshots,
				sessionLocks: immediateSessionLocks(),
				createEventSource: (url) => new FakeEventSource(url),
				visibility: null,
				online: null
			});
			const login = vi.spyOn(room, 'login');
			let page: ReturnType<typeof renderRoomPage> | null = null;

			try {
				page = renderRoomPage(room);
				await waitFor(() => expect(api.whoAmI).toHaveBeenCalledTimes(1));
				await waitFor(() => expect(room.store.status).toBe('auth_required'));
				await clearStarted.promise;
				expect(page.target.querySelector('#room-password')).not.toBeNull();
				expect(room.store.canWrite).toBe(false);

				const input = page.target.querySelector<HTMLInputElement>('#room-password')!;
				input.value = 'secret';
				input.dispatchEvent(new Event('input', { bubbles: true }));
				const form = page.target.querySelector('form')!;
				form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
				flushSync();
				// Commit the initial clear, but hold its notification across the
				// sign-in precheck or request. A durable-clear barrier may now finish.
				allowClear.resolve();
				await hintStarted.promise;
				if (stage === 'precheck') {
					await signInCheckStarted.promise;
					expect(api.login).not.toHaveBeenCalled();
				} else {
					await loginStarted.promise;
					expect(api.login).toHaveBeenCalledTimes(1);
				}

				allowHint.resolve();
				await hintDelivered.promise;
				// Drain the read started by the delivered hint, without assuming
				// that handling our own echo starts a pending-logout scan.
				await snapshots.generation({ kind: 'room', slug: ROOM.slug });
				allowSignInCheck.resolve({ ok: true, value: [] });
				allowLogin.resolve(ROOM);
				expect(login).toHaveBeenCalledTimes(1);
				const signInResult = await login.mock.results[0].value;

				await waitFor(() => {
					const alert = page!.target.querySelector('[role="alert"]')?.textContent ?? null;
					if (room.store.status !== 'ready' && alert !== INTERRUPTED) {
						throw new Error('waiting for sign-in completion or its visible error');
					}
				});

				expect({
					loginRequests: api.login.mock.calls,
					alert: page.target.querySelector('[role="alert"]')?.textContent ?? null,
					status: room.store.status,
					canWrite: room.store.canWrite,
					completedSignIn: signInResult.ok
				}).toEqual({
					loginRequests: [[ROOM.slug, 'secret']],
					alert: null,
					status: 'ready',
					canWrite: true,
					completedSignIn: true
				});
				expect(api.logout).not.toHaveBeenCalled();
			} finally {
				allowClear.resolve();
				allowHint.resolve();
				allowSignInCheck.resolve({ ok: true, value: [] });
				allowLogin.resolve(ROOM);
				if (page) {
					await unmount(page.component);
					page.target.remove();
				}
				snapshots.close();
			}
		}
	);

	it('waits for its durable clear before starting the sign-in precheck', async () => {
		const snapshots = createSnapshotStore({ indexedDB: new IDBFactory(), channel: null });
		const api = fakeRoomApi();
		api.whoAmI.mockRejectedValueOnce(new ApiError(401, 'not_authenticated', 'Sign in.'));
		const started = deferred<void>();
		const allow = deferred<void>();
		const original = snapshots.clear.bind(snapshots);
		vi.spyOn(snapshots, 'clear').mockImplementation(async (...args) => {
			started.resolve();
			await allow.promise;
			return original(...args);
		});
		const checks = vi.spyOn(snapshots, 'pendingServerLogouts');
		const room = new RoomHandle(ROOM.slug, {
			api,
			snapshotStore: snapshots,
			sessionLocks: immediateSessionLocks(),
			createEventSource: (url) => new FakeEventSource(url),
			visibility: null,
			online: null
		});
		room.retain();
		let signingIn: ReturnType<RoomHandle['login']> | undefined;
		try {
			await started.promise;
			signingIn = room.login('secret');
			// Complete a real storage read while the clear is held, not a timed wait.
			await snapshots.generation({ kind: 'room', slug: ROOM.slug });
			expect(checks).not.toHaveBeenCalled();
			expect(api.login).not.toHaveBeenCalled();
			allow.resolve();
			expect(await signingIn).toMatchObject({ ok: true });
			expect(room.store.canWrite).toBe(true);
		} finally {
			allow.resolve();
			await signingIn;
			room.release();
			snapshots.close();
		}
	});

	it.each([false, true])(
		'isolates a switched room from late login (sign-out: %s)',
		async (signOut) => {
			const snapshots = createSnapshotStore({ indexedDB: new IDBFactory(), channel: null });
			const started = deferred<void>();
			const answer = deferred<Room>();
			const oldApi = fakeRoomApi();
			oldApi.login.mockImplementation(async () => {
				started.resolve();
				return answer.promise;
			});
			const other = { ...ROOM, slug: 'other-room', name: 'Other room' };
			const newApi = fakeRoomApi({
				whoAmI: vi.fn(async () => other),
				changes: vi.fn(async () => makeFeed({ room: other, seq: 1, full: true }))
			});
			const options = {
				snapshotStore: snapshots,
				sessionLocks: immediateSessionLocks(),
				createEventSource: (url: string) => new FakeEventSource(url),
				visibility: null,
				online: null
			};
			const oldRoom = new RoomHandle(ROOM.slug, { ...options, api: oldApi });
			const newRoom = new RoomHandle(other.slug, { ...options, api: newApi });
			let page = renderRoomPage(oldRoom);
			try {
				await waitFor(() => expect(oldRoom.store.canWrite).toBe(true));
				const signingIn = oldRoom.login('secret');
				await started.promise;
				if (signOut) expect(await oldRoom.logout()).toMatchObject({ ok: true });
				await unmount(page.component);
				page.target.remove();
				page = renderRoomPage(newRoom);
				await waitFor(() => expect(newRoom.store.canWrite).toBe(true));
				answer.resolve(ROOM);
				expect((await signingIn).ok).toBe(!signOut);
				expect(newRoom.store.room).toEqual(other);
				expect(newRoom.store.status).toBe('ready');
				expect(newRoom.store.canWrite).toBe(true);
				expect(newApi.login).not.toHaveBeenCalled();
				expect(newApi.logout).not.toHaveBeenCalled();
				if (signOut) {
					expect(oldRoom.store.canWrite).toBe(false);
					expect(oldRoom.store.lists).toEqual([]);
					expect(await snapshots.read({ kind: 'room', slug: ROOM.slug })).toMatchObject({
						ok: false,
						reason: 'signed_out'
					});
				}
			} finally {
				answer.resolve(ROOM);
				await unmount(page.component);
				page.target.remove();
				snapshots.close();
			}
		}
	);

	it.each(['clear', 'sign-out'] as const)(
		'keeps a newer external %s fence while its own clear is pending',
		async (kind) => {
			const snapshots = createSnapshotStore({ indexedDB: new IDBFactory(), channel: null });
			const identity = { kind: 'room', slug: ROOM.slug } as const;
			const api = fakeRoomApi();
			api.whoAmI.mockRejectedValueOnce(new ApiError(401, 'not_authenticated', 'Sign in.'));
			const clearStarted = deferred<void>();
			const allowClear = deferred<void>();
			const originalClear = snapshots.clear.bind(snapshots);
			vi.spyOn(snapshots, 'clear').mockImplementation(async (...args) => {
				clearStarted.resolve();
				await allowClear.promise;
				return originalClear(...args);
			});
			const checks = vi.spyOn(snapshots, 'pendingServerLogouts');
			const room = new RoomHandle(ROOM.slug, {
				api,
				snapshotStore: snapshots,
				sessionLocks: immediateSessionLocks(),
				createEventSource: (url) => new FakeEventSource(url),
				visibility: null,
				online: null
			});
			room.retain();
			try {
				await clearStarted.promise;
				const signingIn = room.login('secret');
				if (kind === 'clear') await originalClear(identity);
				else await snapshots.localSignOut(identity);
				// This scan starts only after the external hint revoked the handle.
				await waitFor(() => expect(checks).toHaveBeenCalled());
				allowClear.resolve();
				expect(await signingIn).toMatchObject({ ok: false, code: 'signed_out' });
				expect(api.login).not.toHaveBeenCalled();
				expect(room.store.canWrite).toBe(false);
				expect(room.store.status).toBe('auth_required');
				expect(room.store.lists).toEqual([]);
			} finally {
				allowClear.resolve();
				room.release();
				snapshots.close();
			}
		}
	);

	it.each(['unavailable', 'throws'] as const)(
		'blocks sign-in when its own clear %s',
		async (failure) => {
			const snapshots = createSnapshotStore({ indexedDB: new IDBFactory(), channel: null });
			const api = fakeRoomApi();
			api.whoAmI.mockRejectedValueOnce(new ApiError(401, 'not_authenticated', 'Sign in.'));
			vi.spyOn(snapshots, 'clear').mockImplementation(async () => {
				if (failure === 'throws') throw new Error('storage unavailable');
				return { ok: false, reason: 'unavailable' };
			});
			const room = new RoomHandle(ROOM.slug, {
				api,
				snapshotStore: snapshots,
				sessionLocks: immediateSessionLocks(),
				createEventSource: (url) => new FakeEventSource(url),
				visibility: null,
				online: null
			});
			room.retain();
			try {
				await waitFor(() => expect(snapshots.clear).toHaveBeenCalled());
				expect(await room.login('secret')).toMatchObject({
					ok: false,
					code: 'session_transition_unavailable'
				});
				expect(api.login).not.toHaveBeenCalled();
				expect(room.store.canWrite).toBe(false);
				expect(room.store.status).toBe('auth_required');
			} finally {
				room.release();
				snapshots.close();
			}
		}
	);
});
