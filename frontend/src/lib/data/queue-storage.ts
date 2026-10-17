// Where a room's queued ops wait on this device (plans/offline-editing.md, 6.2c).
//
// One IndexedDB object store ("queue"), one record per room or share link:
//   key: "room:<slug>" or "share:<token>"   (rooms and share links never mix)
//   entries: StoredEntry[] in send order     (see queue-entries.ts)
// Each change is one read-modify-write transaction, so two tabs cannot lose an
// entry. Without IndexedDB (or after a failure) entries live in memory and
// `durable` is false.
//
// Methods never reject: a storage failure switches to memory and the queue goes on.

import { isRecord } from './snapshot-validate';
import { requestValue, transact } from './snapshot-idb';
import type { EntryState, StoredEntry } from './queue-entries';
import type { SentOp } from './types';

export const QUEUE_DATABASE_NAME = 'listr-queue';
const QUEUE_DATABASE_VERSION = 1;
const QUEUE_STORE = 'queue';

export interface QueueStorage {
	/** False when entries are kept in memory only. */
	readonly durable: boolean;
	/** Entries in send order. */
	read(): Promise<StoredEntry[]>;
	add(entry: StoredEntry): Promise<void>;
	remove(opId: string): Promise<void>;
	setState(opId: string, state: EntryState): Promise<void>;
	/** Marks an entry as sent: its request is about to go out (see StoredEntry.sent). */
	setSent(opId: string): Promise<void>;
	/** Replaces the op JSON of an entry (its `op_id` stays). */
	setOp(opId: string, op: SentOp): Promise<void>;
	/** Removes every entry of this room or share link. */
	clear(): Promise<void>;
}

/** Entries in memory only: no IndexedDB, or for tests. Lost on reload. */
export class MemoryQueueStorage implements QueueStorage {
	readonly durable = false;
	#entries: StoredEntry[] = [];

	async read(): Promise<StoredEntry[]> {
		return this.#entries.slice();
	}
	async add(entry: StoredEntry): Promise<void> {
		this.#entries = [...this.#entries, entry];
	}
	async remove(opId: string): Promise<void> {
		this.#entries = this.#entries.filter((entry) => entry.opId !== opId);
	}
	async setState(opId: string, state: EntryState): Promise<void> {
		this.#entries = this.#entries.map((entry) =>
			entry.opId === opId ? { ...entry, state } : entry
		);
	}
	async setSent(opId: string): Promise<void> {
		this.#entries = this.#entries.map((entry) =>
			entry.opId === opId ? { ...entry, sent: true } : entry
		);
	}
	async setOp(opId: string, op: SentOp): Promise<void> {
		this.#entries = this.#entries.map((entry) => (entry.opId === opId ? { ...entry, op } : entry));
	}
	async clear(): Promise<void> {
		this.#entries = [];
	}
}

interface StoredRecord {
	key: string;
	entries: unknown[];
}

export function openQueueDatabase(factory: IDBFactory, name: string): Promise<IDBDatabase> {
	return new Promise((resolve, reject) => {
		let request: IDBOpenDBRequest;
		try {
			request = factory.open(name, QUEUE_DATABASE_VERSION);
		} catch (error) {
			reject(error);
			return;
		}
		let finished = false;
		request.onupgradeneeded = () => {
			const database = request.result;
			if (!database.objectStoreNames.contains(QUEUE_STORE))
				database.createObjectStore(QUEUE_STORE, { keyPath: 'key' });
		};
		request.onsuccess = () => {
			if (finished) {
				request.result.close();
				return;
			}
			finished = true;
			request.result.onversionchange = () => request.result.close();
			resolve(request.result);
		};
		request.onerror = () => {
			if (finished) return;
			finished = true;
			reject(request.error ?? new Error('IndexedDB could not be opened'));
		};
		request.onblocked = () => {
			if (finished) return;
			finished = true;
			reject(new Error('IndexedDB upgrade is blocked'));
		};
	});
}

/** The raw entries of a stored record; anything else counts as empty. */
function entriesOf(record: unknown): unknown[] {
	return isRecord(record) && Array.isArray(record.entries) ? record.entries : [];
}

/** Keeps the raw items that have an `opId`. Others stay in the record but are not shown. */
function parseEntries(raw: unknown[]): StoredEntry[] {
	return raw.filter((item): item is StoredEntry => isRecord(item) && typeof item.opId === 'string');
}

function sameOp(item: unknown, opId: string): item is Record<string, unknown> {
	return isRecord(item) && item.opId === opId;
}

class IndexedDbQueueStorage implements QueueStorage {
	readonly #key: string;
	readonly #factory: IDBFactory;
	readonly #name: string;
	#database: Promise<IDBDatabase> | null = null;
	/** Last known entries: the answer when IndexedDB fails. */
	#memory: StoredEntry[] = [];
	/** Sticky: once IndexedDB failed, this page keeps its entries in memory. */
	#failed = false;

	constructor(key: string, factory: IDBFactory, name: string) {
		this.#key = key;
		this.#factory = factory;
		this.#name = name;
	}

	get durable(): boolean {
		return !this.#failed;
	}

	async read(): Promise<StoredEntry[]> {
		if (!this.#failed) {
			try {
				const database = await this.#open();
				this.#memory = await transact(database, QUEUE_STORE, 'readonly', async (tx) => {
					const record = await requestValue(tx.objectStore(QUEUE_STORE).get(this.#key));
					return parseEntries(entriesOf(record));
				});
			} catch {
				this.#failed = true;
			}
		}
		return this.#memory.slice();
	}

	add(entry: StoredEntry): Promise<void> {
		return this.#change(
			(raw) => [...raw, entry],
			(memory) => [...memory, entry]
		);
	}

	remove(opId: string): Promise<void> {
		return this.#change(
			(raw) => raw.filter((item) => !sameOp(item, opId)),
			(memory) => memory.filter((entry) => entry.opId !== opId)
		);
	}

	setState(opId: string, state: EntryState): Promise<void> {
		return this.#change(
			(raw) => raw.map((item) => (sameOp(item, opId) ? { ...item, state } : item)),
			(memory) => memory.map((entry) => (entry.opId === opId ? { ...entry, state } : entry))
		);
	}

	setSent(opId: string): Promise<void> {
		return this.#change(
			(raw) => raw.map((item) => (sameOp(item, opId) ? { ...item, sent: true } : item)),
			(memory) => memory.map((entry) => (entry.opId === opId ? { ...entry, sent: true } : entry))
		);
	}

	setOp(opId: string, op: SentOp): Promise<void> {
		return this.#change(
			(raw) => raw.map((item) => (sameOp(item, opId) ? { ...item, op } : item)),
			(memory) => memory.map((entry) => (entry.opId === opId ? { ...entry, op } : entry))
		);
	}

	clear(): Promise<void> {
		return this.#change(
			() => [],
			() => []
		);
	}

	#open(): Promise<IDBDatabase> {
		this.#database ??= openQueueDatabase(this.#factory, this.#name).then((database) => {
			askPersistentStorage();
			return database;
		});
		return this.#database;
	}

	/** One read-modify-write transaction on the room's record. */
	async #change(
		change: (raw: unknown[]) => unknown[],
		fallback: (memory: StoredEntry[]) => StoredEntry[]
	): Promise<void> {
		if (!this.#failed) {
			try {
				const database = await this.#open();
				this.#memory = await transact(database, QUEUE_STORE, 'readwrite', async (tx) => {
					const store = tx.objectStore(QUEUE_STORE);
					const record = await requestValue(store.get(this.#key));
					const entries = change(entriesOf(record));
					if (entries.length === 0) await requestValue(store.delete(this.#key));
					else await requestValue(store.put({ key: this.#key, entries } satisfies StoredRecord));
					return parseEntries(entries);
				});
				return;
			} catch {
				this.#failed = true;
			}
		}
		this.#memory = fallback(this.#memory);
	}
}

let persistAsked = false;

/**
 * Asks the browser to keep this origin's data (R11). Asked once per page load;
 * a refusal or a missing API is ignored.
 */
function askPersistentStorage(): void {
	if (persistAsked) return;
	persistAsked = true;
	void Promise.resolve()
		.then(() => navigator.storage?.persist?.())
		.catch(() => undefined);
}

export interface QueueStorageOptions {
	/** Inject fake-indexeddb in tests. `null` forces memory. */
	indexedDB?: IDBFactory | null;
	databaseName?: string;
}

/** The storage for one room (`room:<slug>`) or share link (`share:<token>`). */
export function createQueueStorage(key: string, options: QueueStorageOptions = {}): QueueStorage {
	const factory =
		options.indexedDB === undefined
			? typeof indexedDB === 'undefined'
				? null
				: indexedDB
			: options.indexedDB;
	if (!factory) return new MemoryQueueStorage();
	return new IndexedDbQueueStorage(key, factory, options.databaseName ?? QUEUE_DATABASE_NAME);
}
