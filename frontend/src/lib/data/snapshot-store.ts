import type { Item, List, Room } from '#lib/data/types.ts';
import { CONTROLS, ROUTING, SNAPSHOTS, openDatabase, requestValue, transact } from './snapshot-idb';
import {
	isRecord,
	isSequence,
	nonEmptyString,
	parseClearHint,
	sameIdentity,
	validControl,
	validIdentity,
	validateData,
	type StoredControl
} from './snapshot-validate';

export const SNAPSHOT_SCHEMA_VERSION = 1;
const DEFAULT_DATABASE_NAME = 'listr-snapshots';
const LAST_ROOM_KEY = 'last-room';

export type RoomIdentity = { kind: 'room'; slug: string };
export type ShareIdentity = { kind: 'share'; token: string };
export type SnapshotIdentity = RoomIdentity | ShareIdentity;

/** A complete, committed server view. Pending operations and auth state do not belong here. */
export interface SnapshotData {
	seq: number;
	room: Room | null;
	lists: List[];
	items: Item[];
}

export interface SavedSnapshot extends SnapshotData {
	schemaVersion: typeof SNAPSHOT_SCHEMA_VERSION;
	identity: SnapshotIdentity;
	savedAt: string;
}

export interface SnapshotGeneration {
	identityKey: string;
	generation: number;
}

export type SnapshotFailureReason =
	'unavailable' | 'signed_out' | 'stale' | 'invalid_identity' | 'invalid_snapshot';

export type SnapshotResult<T> =
	{ ok: true; value: T } | { ok: false; reason: SnapshotFailureReason };

/** The event is only a cross-tab hint; durable control records decide access and staleness. */
export interface SnapshotClearHint {
	identity: SnapshotIdentity;
	generation: number;
}

export interface SnapshotClearChannel {
	postMessage(message: unknown): void;
	addEventListener(type: 'message', listener: (event: MessageEvent) => void): void;
	removeEventListener(type: 'message', listener: (event: MessageEvent) => void): void;
	close(): void;
}

export interface SnapshotStore {
	generation(identity: SnapshotIdentity): Promise<SnapshotResult<SnapshotGeneration>>;
	read(identity: SnapshotIdentity): Promise<SnapshotResult<SavedSnapshot | null>>;
	save(
		identity: SnapshotIdentity,
		data: SnapshotData,
		generation: SnapshotGeneration
	): Promise<SnapshotResult<SavedSnapshot>>;
	clear(identity: SnapshotIdentity): Promise<SnapshotResult<void>>;
	localSignOut(identity: RoomIdentity): Promise<SnapshotResult<void>>;
	pendingServerLogouts(): Promise<SnapshotResult<RoomIdentity[]>>;
	acknowledgeServerLogout(identity: RoomIdentity): Promise<SnapshotResult<void>>;
	clearSignOutAfterSignIn(identity: RoomIdentity): Promise<SnapshotResult<void>>;
	/** A routing hint only; callers must still revalidate server access. */
	lastRoom(): Promise<SnapshotResult<string | null>>;
	onClear(listener: (hint: SnapshotClearHint) => void): () => void;
	close(): void;
}

export interface SnapshotStoreOptions {
	/** Inject fake-indexeddb or another IDBFactory for tests. */
	indexedDB?: IDBFactory | null;
	databaseName?: string;
	now?: () => Date;
	/** Pass null to disable cross-tab hints in tests or non-browser environments. */
	channel?: SnapshotClearChannel | null;
}

interface StoredSnapshot {
	key: string;
	identity: SnapshotIdentity;
	value: unknown;
}

interface IdentityKey {
	identity: SnapshotIdentity;
	key: string;
}

function identify(identity: SnapshotIdentity): IdentityKey | null {
	if (!validIdentity(identity)) return null;
	const copy: SnapshotIdentity =
		identity.kind === 'room'
			? { kind: 'room', slug: identity.slug }
			: { kind: 'share', token: identity.token };
	return {
		identity: copy,
		key: `${copy.kind}:${encodeURIComponent('slug' in copy ? copy.slug : copy.token)}`
	};
}

function readSnapshot(identity: SnapshotIdentity, value: unknown): SavedSnapshot | null {
	if (!isRecord(value) || value.schemaVersion !== SNAPSHOT_SCHEMA_VERSION || !isSequence(value.seq))
		return null;
	if (!validIdentity(value.identity) || !sameIdentity(value.identity, identity)) return null;
	if (typeof value.savedAt !== 'string' || !Number.isFinite(Date.parse(value.savedAt))) return null;
	const data = validateData(identity, value);
	if (!data) return null;
	return {
		schemaVersion: SNAPSHOT_SCHEMA_VERSION,
		identity: { ...identity },
		...data,
		savedAt: value.savedAt
	};
}

function resultFailure<T>(reason: SnapshotFailureReason): SnapshotResult<T> {
	return { ok: false, reason };
}

function resultSuccess<T>(value: T): SnapshotResult<T> {
	return { ok: true, value };
}

/**
 * Validates the stored control record and computes the next generation.
 * Call it right after reading the record, before any other await, so the
 * read and the bump stay in the same transaction step.
 */
function nextGeneration(
	raw: unknown,
	identified: IdentityKey
): SnapshotResult<{ old: StoredControl | undefined; generation: number }> {
	if (raw !== undefined && !validControl(raw, identified.key, identified.identity)) {
		return resultFailure('unavailable');
	}
	const old = raw as StoredControl | undefined;
	const generation = (old?.generation ?? 0) + 1;
	if (!isSequence(generation)) return resultFailure('unavailable');
	return resultSuccess({ old, generation });
}

export function createSnapshotStore(options: SnapshotStoreOptions = {}): SnapshotStore {
	const databaseName = options.databaseName ?? DEFAULT_DATABASE_NAME;
	const factory =
		options.indexedDB === undefined
			? typeof indexedDB === 'undefined'
				? null
				: indexedDB
			: options.indexedDB;
	let databasePromise: Promise<IDBDatabase> | null = null;
	let channel: SnapshotClearChannel | null = options.channel ?? null;
	if (options.channel === undefined && typeof BroadcastChannel !== 'undefined') {
		try {
			channel = new BroadcastChannel(`${databaseName}:clear-hints`);
		} catch {
			channel = null;
		}
	}
	const listeners = new Set<(hint: SnapshotClearHint) => void>();

	const receiveClearHint = (event: MessageEvent) => {
		const hint = parseClearHint(event.data);
		if (!hint) return;
		for (const listener of listeners) {
			try {
				listener(hint);
			} catch {
				// A notification consumer cannot interrupt another consumer.
			}
		}
	};
	channel?.addEventListener('message', receiveClearHint);

	function database(): Promise<IDBDatabase> {
		if (!factory) return Promise.reject(new Error('IndexedDB is unavailable'));
		if (!databasePromise) {
			databasePromise = openDatabase(factory, databaseName).catch((error: unknown) => {
				databasePromise = null;
				throw error;
			});
		}
		return databasePromise;
	}

	function publishClear(identity: SnapshotIdentity, generation: number): void {
		const hint: SnapshotClearHint = { identity, generation };
		for (const listener of listeners) {
			try {
				listener(hint);
			} catch {
				// Durable state has already changed; notifications are advisory.
			}
		}
		try {
			channel?.postMessage({ type: 'snapshot-clear', ...hint });
		} catch {
			// Durable IndexedDB state is authoritative; notification failure is harmless.
		}
	}

	async function invalidate(
		identity: RoomIdentity,
		markSignedOut: boolean
	): Promise<SnapshotResult<void>> {
		const identified = identify(identity);
		if (!identified || identified.identity.kind !== 'room')
			return resultFailure('invalid_identity');
		const roomIdentity = identified.identity;
		try {
			const db = await database();
			const changed = await transact<SnapshotResult<number>>(
				db,
				[CONTROLS, SNAPSHOTS, ROUTING],
				'readwrite',
				async (tx) => {
					const controls = tx.objectStore(CONTROLS);
					const raw = await requestValue(controls.get(identified.key));
					const next = nextGeneration(raw, identified);
					if (!next.ok) return next;
					const { old, generation } = next.value;
					const control: StoredControl = {
						key: identified.key,
						identity: identified.identity,
						generation
					};
					if (markSignedOut) control.signOut = { pendingServerLogout: true };
					else if (old?.signOut) control.signOut = old.signOut;
					await requestValue(controls.put(control));
					await requestValue(tx.objectStore(SNAPSHOTS).delete(identified.key));
					const routing = tx.objectStore(ROUTING);
					const hint = await requestValue(routing.get(LAST_ROOM_KEY));
					if (isRecord(hint) && hint.slug === roomIdentity.slug) {
						await requestValue(routing.delete(LAST_ROOM_KEY));
					}
					return resultSuccess(generation);
				}
			);
			if (!changed.ok) return changed;
			publishClear(roomIdentity, changed.value);
			return resultSuccess(undefined);
		} catch {
			return resultFailure('unavailable');
		}
	}

	return {
		async generation(identity) {
			const identified = identify(identity);
			if (!identified) return resultFailure('invalid_identity');
			try {
				const db = await database();
				return await transact(db, CONTROLS, 'readwrite', async (tx) => {
					const controls = tx.objectStore(CONTROLS);
					const raw = await requestValue(controls.get(identified.key));
					let control: StoredControl;
					if (raw === undefined) {
						control = { key: identified.key, identity: identified.identity, generation: 0 };
						await requestValue(controls.put(control));
					} else if (!validControl(raw, identified.key, identified.identity)) {
						return resultFailure('unavailable');
					} else {
						control = raw;
					}
					if (control.signOut) return resultFailure('signed_out');
					return resultSuccess({ identityKey: identified.key, generation: control.generation });
				});
			} catch {
				return resultFailure('unavailable');
			}
		},

		async read(identity) {
			const identified = identify(identity);
			if (!identified) return resultFailure('invalid_identity');
			try {
				const db = await database();
				return await transact(db, [CONTROLS, SNAPSHOTS], 'readwrite', async (tx) => {
					const controls = tx.objectStore(CONTROLS);
					const snapshots = tx.objectStore(SNAPSHOTS);
					const [rawControl, rawSnapshot] = await Promise.all([
						requestValue(controls.get(identified.key)),
						requestValue(snapshots.get(identified.key))
					]);
					if (
						rawControl !== undefined &&
						!validControl(rawControl, identified.key, identified.identity)
					) {
						return resultFailure('unavailable');
					}
					const control = rawControl as StoredControl | undefined;
					if (control?.signOut) return resultFailure('signed_out');
					if (rawSnapshot === undefined) return resultSuccess(null);
					if (!control) {
						await requestValue(snapshots.delete(identified.key));
						return resultSuccess(null);
					}
					const stored = rawSnapshot as StoredSnapshot;
					const snapshot =
						isRecord(stored) &&
						stored.key === identified.key &&
						validIdentity(stored.identity) &&
						sameIdentity(stored.identity, identified.identity)
							? readSnapshot(identified.identity, stored.value)
							: null;
					if (!snapshot) await requestValue(snapshots.delete(identified.key));
					return resultSuccess(snapshot);
				});
			} catch {
				return resultFailure('unavailable');
			}
		},

		async save(identity, data, token) {
			const identified = identify(identity);
			if (!identified) return resultFailure('invalid_identity');
			if (!token || token.identityKey !== identified.key || !isSequence(token.generation)) {
				return resultFailure('stale');
			}
			const validated = validateData(identified.identity, data);
			if (!validated) return resultFailure('invalid_snapshot');
			let savedAt: string;
			try {
				savedAt = (options.now?.() ?? new Date()).toISOString();
			} catch {
				return resultFailure('unavailable');
			}
			const value: SavedSnapshot = {
				schemaVersion: SNAPSHOT_SCHEMA_VERSION,
				identity: identified.identity,
				...validated,
				savedAt
			};
			try {
				const db = await database();
				return await transact(db, [CONTROLS, SNAPSHOTS, ROUTING], 'readwrite', async (tx) => {
					const raw = await requestValue(tx.objectStore(CONTROLS).get(identified.key));
					if (!validControl(raw, identified.key, identified.identity)) {
						return resultFailure('unavailable');
					}
					if (raw.signOut) return resultFailure('signed_out');
					if (raw.generation !== token.generation) return resultFailure('stale');
					await requestValue(
						tx.objectStore(SNAPSHOTS).put({
							key: identified.key,
							identity: identified.identity,
							value
						} satisfies StoredSnapshot)
					);
					if (identified.identity.kind === 'room') {
						await requestValue(
							tx.objectStore(ROUTING).put({
								key: LAST_ROOM_KEY,
								slug: identified.identity.slug
							})
						);
					}
					return resultSuccess(value);
				});
			} catch {
				return resultFailure('unavailable');
			}
		},

		async clear(identity) {
			const identified = identify(identity);
			if (!identified) return resultFailure('invalid_identity');
			try {
				const db = await database();
				const result = await transact<SnapshotResult<number>>(
					db,
					[CONTROLS, SNAPSHOTS, ROUTING],
					'readwrite',
					async (tx) => {
						const controls = tx.objectStore(CONTROLS);
						const raw = await requestValue(controls.get(identified.key));
						const next = nextGeneration(raw, identified);
						if (!next.ok) return next;
						const { old, generation } = next.value;
						const control: StoredControl = {
							key: identified.key,
							identity: identified.identity,
							generation
						};
						if (old?.signOut) control.signOut = old.signOut;
						await requestValue(controls.put(control));
						await requestValue(tx.objectStore(SNAPSHOTS).delete(identified.key));
						if (identified.identity.kind === 'room') {
							const routing = tx.objectStore(ROUTING);
							const hint = await requestValue(routing.get(LAST_ROOM_KEY));
							if (isRecord(hint) && hint.slug === identified.identity.slug) {
								await requestValue(routing.delete(LAST_ROOM_KEY));
							}
						}
						return resultSuccess(generation);
					}
				);
				if (!result.ok) return result;
				publishClear(identified.identity, result.value);
				return resultSuccess(undefined);
			} catch {
				return resultFailure('unavailable');
			}
		},

		localSignOut(identity) {
			return invalidate(identity, true);
		},

		async pendingServerLogouts() {
			try {
				const db = await database();
				return await transact(db, CONTROLS, 'readonly', async (tx) => {
					const controls = await requestValue(tx.objectStore(CONTROLS).getAll());
					const pending: RoomIdentity[] = [];
					for (const control of controls) {
						if (
							!isRecord(control) ||
							!validIdentity(control.identity) ||
							!validControl(control, identify(control.identity)!.key, control.identity)
						) {
							return resultFailure('unavailable');
						}
						if (control.identity.kind === 'room' && control.signOut?.pendingServerLogout) {
							pending.push({ kind: 'room', slug: control.identity.slug });
						}
					}
					return resultSuccess(pending);
				});
			} catch {
				return resultFailure('unavailable');
			}
		},

		async acknowledgeServerLogout(identity) {
			const identified = identify(identity);
			if (!identified || identified.identity.kind !== 'room')
				return resultFailure('invalid_identity');
			try {
				const db = await database();
				return await transact(db, CONTROLS, 'readwrite', async (tx) => {
					const controls = tx.objectStore(CONTROLS);
					const raw = await requestValue(controls.get(identified.key));
					if (raw === undefined) return resultSuccess(undefined);
					if (!validControl(raw, identified.key, identified.identity))
						return resultFailure('unavailable');
					if (raw.signOut?.pendingServerLogout) {
						await requestValue(
							controls.put({
								...raw,
								signOut: { pendingServerLogout: false }
							} satisfies StoredControl)
						);
					}
					return resultSuccess(undefined);
				});
			} catch {
				return resultFailure('unavailable');
			}
		},

		async clearSignOutAfterSignIn(identity) {
			const identified = identify(identity);
			if (!identified || identified.identity.kind !== 'room')
				return resultFailure('invalid_identity');
			try {
				const db = await database();
				return await transact(db, CONTROLS, 'readwrite', async (tx) => {
					const controls = tx.objectStore(CONTROLS);
					const raw = await requestValue(controls.get(identified.key));
					const next = nextGeneration(raw, identified);
					if (!next.ok) return next;
					const { generation } = next.value;
					await requestValue(
						controls.put({
							key: identified.key,
							identity: identified.identity,
							generation
						} satisfies StoredControl)
					);
					return resultSuccess(undefined);
				});
			} catch {
				return resultFailure('unavailable');
			}
		},

		async lastRoom() {
			try {
				const db = await database();
				return await transact(db, ROUTING, 'readwrite', async (tx) => {
					const routing = tx.objectStore(ROUTING);
					const read = await requestValue(routing.get(LAST_ROOM_KEY));
					if (read === undefined) return resultSuccess(null);
					if (isRecord(read) && read.key === LAST_ROOM_KEY && nonEmptyString(read.slug)) {
						return resultSuccess(read.slug);
					}
					await requestValue(routing.delete(LAST_ROOM_KEY));
					return resultSuccess(null);
				});
			} catch {
				return resultFailure('unavailable');
			}
		},

		onClear(listener) {
			listeners.add(listener);
			return () => listeners.delete(listener);
		},

		close() {
			channel?.removeEventListener('message', receiveClearHint);
			channel?.close();
			channel = null;
			listeners.clear();
			databasePromise?.then((db) => db.close()).catch(() => undefined);
			databasePromise = null;
		}
	};
}
