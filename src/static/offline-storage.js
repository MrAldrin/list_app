(() => {
  'use strict';

  const DB_NAME = 'listr-offline';
  const DB_VERSION = 1;
  const STORE_NAME = 'snapshots';
  const RECORD_KEY = 'current';
  const RECORD_VERSION = 1;
  const SNAPSHOT_VERSION = 1;
  const MAX_LISTS = 200;
  const MAX_ITEMS = 5000;
  const MAX_BYTES = 1024 * 1024;

  function isRecord(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function hasExactKeys(value, allowedKeys) {
    if (!isRecord(value)) return false;
    const actual = Object.keys(value).sort();
    const expected = [...allowedKeys].sort();
    return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
  }

  function isStringArray(value) {
    return Array.isArray(value) && value.every((entry) => typeof entry === 'string');
  }

  function validateSnapshot(snapshot, requestedSlug) {
    if (!hasExactKeys(snapshot, ['schema_version', 'room', 'lists'])) return false;
    if (snapshot.schema_version !== SNAPSHOT_VERSION || !Array.isArray(snapshot.lists)) return false;
    if (!hasExactKeys(snapshot.room, ['slug', 'name'])) return false;
    if (snapshot.room.slug !== requestedSlug || typeof snapshot.room.name !== 'string') return false;
    if (snapshot.lists.length > MAX_LISTS) return false;

    let itemCount = 0;
    for (const list of snapshot.lists) {
      if (!hasExactKeys(list, ['name', 'list_tags', 'items'])) return false;
      if (typeof list.name !== 'string' || !isStringArray(list.list_tags) || !Array.isArray(list.items)) return false;
      itemCount += list.items.length;
      if (itemCount > MAX_ITEMS) return false;
      for (const item of list.items) {
        if (!hasExactKeys(item, ['name', 'done', 'active_tags', 'description', 'quantity'])) return false;
        if (typeof item.name !== 'string' || typeof item.done !== 'boolean') return false;
        if (!isStringArray(item.active_tags) || typeof item.description !== 'string') return false;
        if (!Number.isSafeInteger(item.quantity) || item.quantity < 1) return false;
      }
    }

    try {
      return new TextEncoder().encode(JSON.stringify(snapshot)).byteLength <= MAX_BYTES;
    } catch (_) {
      return false;
    }
  }

  function validStoredRecord(record) {
    return hasExactKeys(record, ['schema_version', 'saved_at', 'snapshot'])
      && record.schema_version === RECORD_VERSION
      && typeof record.saved_at === 'string'
      && Number.isFinite(Date.parse(record.saved_at))
      && new Date(record.saved_at).toISOString() === record.saved_at
      && isRecord(record.snapshot)
      && typeof record.snapshot.room?.slug === 'string'
      && validateSnapshot(record.snapshot, record.snapshot.room.slug);
  }

  function openDatabase() {
    return new Promise((resolve, reject) => {
      let request;
      try {
        request = indexedDB.open(DB_NAME, DB_VERSION);
      } catch (error) {
        reject(error);
        return;
      }
      request.onupgradeneeded = () => {
        const database = request.result;
        if (!database.objectStoreNames.contains(STORE_NAME)) {
          database.createObjectStore(STORE_NAME);
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('IndexedDB could not open'));
      request.onblocked = () => reject(new Error('IndexedDB upgrade is blocked'));
    });
  }

  async function readRecord() {
    const database = await openDatabase();
    try {
      return await new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE_NAME, 'readonly');
        let record;
        const request = transaction.objectStore(STORE_NAME).get(RECORD_KEY);
        request.onsuccess = () => { record = request.result; };
        request.onerror = () => reject(request.error || new Error('Offline copy could not be read'));
        transaction.oncomplete = () => resolve(validStoredRecord(record) ? record : null);
        transaction.onerror = () => reject(transaction.error || new Error('Offline copy could not be read'));
        transaction.onabort = () => reject(transaction.error || new Error('Offline copy read was aborted'));
      });
    } finally {
      database.close();
    }
  }

  async function saveRecord(snapshot) {
    if (!isRecord(snapshot?.room) || !validateSnapshot(snapshot, snapshot.room.slug)) {
      throw new Error('Snapshot is invalid');
    }
    const database = await openDatabase();
    try {
      const record = {
        schema_version: RECORD_VERSION,
        saved_at: new Date().toISOString(),
        snapshot,
      };
      await new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE_NAME, 'readwrite');
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error || new Error('Offline copy could not be saved'));
        transaction.onabort = () => reject(transaction.error || new Error('Offline copy save was aborted'));
        try {
          transaction.objectStore(STORE_NAME).put(record, RECORD_KEY);
        } catch (error) {
          try { transaction.abort(); } catch (_) { /* The transaction may already be inactive. */ }
          reject(error);
        }
      });
      return record;
    } finally {
      database.close();
    }
  }

  async function clearRecordForRoom(slug) {
    const database = await openDatabase();
    try {
      return await new Promise((resolve, reject) => {
        const transaction = database.transaction(STORE_NAME, 'readwrite');
        let removed = false;
        const request = transaction.objectStore(STORE_NAME).get(RECORD_KEY);
        request.onsuccess = () => {
          if (request.result?.snapshot?.room?.slug === slug) {
            transaction.objectStore(STORE_NAME).delete(RECORD_KEY);
            removed = true;
          }
        };
        request.onerror = () => reject(request.error || new Error('Offline copy could not be checked'));
        transaction.oncomplete = () => resolve(removed);
        transaction.onerror = () => reject(transaction.error || new Error('Offline copy could not be cleared'));
        transaction.onabort = () => reject(transaction.error || new Error('Offline copy clear was aborted'));
      });
    } finally {
      database.close();
    }
  }

  window.ListROfflineStorage = Object.freeze({
    validateSnapshot,
    readRecord,
    saveRecord,
    clearRecordForRoom,
  });
})();
