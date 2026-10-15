export const DATABASE_VERSION = 1;
export const SNAPSHOTS = 'snapshots';
export const CONTROLS = 'controls';
export const ROUTING = 'routing';

export function requestValue<T>(request: IDBRequest<T>): Promise<T> {
	return new Promise((resolve, reject) => {
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error ?? new Error('IndexedDB request failed'));
	});
}

export function transactionDone(transaction: IDBTransaction): Promise<void> {
	return new Promise((resolve, reject) => {
		transaction.oncomplete = () => resolve();
		transaction.onabort = () =>
			reject(transaction.error ?? new Error('IndexedDB transaction aborted'));
		transaction.onerror = () =>
			reject(transaction.error ?? new Error('IndexedDB transaction failed'));
	});
}

export async function transact<T>(
	database: IDBDatabase,
	storeNames: string | string[],
	mode: IDBTransactionMode,
	operation: (transaction: IDBTransaction) => Promise<T>
): Promise<T> {
	const transaction = database.transaction(storeNames, mode);
	const done = transactionDone(transaction);
	try {
		const result = await operation(transaction);
		await done;
		return result;
	} catch (error) {
		try {
			transaction.abort();
		} catch {
			// The transaction may already have completed or aborted.
		}
		await done.catch(() => undefined);
		throw error;
	}
}

export function openDatabase(factory: IDBFactory, name: string): Promise<IDBDatabase> {
	return new Promise((resolve, reject) => {
		let request: IDBOpenDBRequest;
		try {
			request = factory.open(name, DATABASE_VERSION);
		} catch (error) {
			reject(error);
			return;
		}
		let finished = false;
		request.onupgradeneeded = () => {
			const database = request.result;
			if (!database.objectStoreNames.contains(SNAPSHOTS))
				database.createObjectStore(SNAPSHOTS, { keyPath: 'key' });
			if (!database.objectStoreNames.contains(CONTROLS))
				database.createObjectStore(CONTROLS, { keyPath: 'key' });
			if (!database.objectStoreNames.contains(ROUTING))
				database.createObjectStore(ROUTING, { keyPath: 'key' });
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
