(() => {
  'use strict';

  const storage = window.ListROfflineStorage;
  const REQUEST_TIMEOUT_MS = 5000;
  const SNAPSHOT_PATH = '/api/offline/rooms/';

  function formatTime(record) {
    const time = new Date(record.saved_at);
    return Number.isNaN(time.getTime()) ? 'unknown time' : time.toLocaleString();
  }

  function setMessage(message) {
    document.getElementById('status').textContent = message;
  }

  function showLastSaved(record) {
    document.getElementById('last-saved').textContent = `Last saved: ${formatTime(record)}`;
  }

  function addText(parent, tag, text, className) {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    parent.append(element);
    return element;
  }

  function renderSnapshot(record) {
    const snapshot = record.snapshot;
    document.getElementById('room-name').textContent = snapshot.room.name;
    showLastSaved(record);
    const lists = document.getElementById('lists');
    lists.replaceChildren();

    for (const list of snapshot.lists) {
      const section = document.createElement('section');
      section.className = 'list-card';
      addText(section, 'h2', list.name);
      if (list.list_tags.length) {
        addText(section, 'p', `Tags: ${list.list_tags.join(', ')}`, 'list-tags');
      }
      const items = document.createElement('ul');
      items.className = 'items';
      for (const item of list.items) {
        const row = document.createElement('li');
        if (item.done) row.classList.add('done');
        const name = document.createElement('span');
        name.textContent = item.name;
        row.append(name);
        const quantity = document.createElement('span');
        quantity.className = 'quantity';
        quantity.textContent = ` · quantity ${item.quantity}`;
        row.append(quantity);
        if (item.description) {
          const details = document.createElement('span');
          details.className = 'item-details';
          details.textContent = ` — ${item.description}`;
          row.append(details);
        }
        if (item.active_tags.length) {
          const tags = document.createElement('span');
          tags.className = 'item-details';
          tags.textContent = ` — Tags: ${item.active_tags.join(', ')}`;
          row.append(tags);
        }
        items.append(row);
      }
      section.append(items);
      lists.append(section);
    }
  }

  function requestedSlug() {
    if (window.location.pathname === '/') return null;
    const match = /^\/room\/([^/]+)\/?$/.exec(window.location.pathname);
    if (!match) return undefined;
    try {
      return decodeURIComponent(match[1]);
    } catch (_) {
      return undefined;
    }
  }

  async function refreshOnline(slug) {
    const headers = new Headers({ Accept: 'application/json' });
    try {
      const token = window.localStorage.getItem(`listapp_room_token_${slug}`);
      if (token) headers.set('X-Listapp-Room-Token', token);
    } catch (_) {
      // HTTPS remembered access is normally the HttpOnly cookie.
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    let response;
    try {
      response = await fetch(`${SNAPSHOT_PATH}${encodeURIComponent(slug)}/snapshot`, {
        method: 'GET',
        credentials: 'same-origin',
        mode: 'same-origin',
        cache: 'no-store',
        redirect: 'error',
        referrerPolicy: 'no-referrer',
        headers,
        signal: controller.signal,
      });
    } finally {
      window.clearTimeout(timeout);
    }

    if (response.status === 401) {
      try { await storage.clearRecordForRoom(slug); } catch (_) { /* Denied copies are never rendered. */ }
      return { kind: 'denied' };
    }
    if (response.status === 403) return { kind: 'denied' };
    if (!response.ok) return { kind: 'temporary-failure' };

    let snapshot;
    try {
      snapshot = await response.json();
    } catch (_) {
      return { kind: 'temporary-failure' };
    }
    if (!storage.validateSnapshot(snapshot, slug)) return { kind: 'temporary-failure' };

    try {
      const saved = await storage.saveRecord(snapshot);
      return { kind: 'saved', record: saved };
    } catch (_) {
      return { kind: 'storage-failure' };
    }
  }

  async function showSavedCopy(slug, state) {
    let record;
    try {
      record = await storage.readRecord();
    } catch (_) {
      setMessage('Offline copy could not be read on this device.');
      document.getElementById('last-saved').textContent = '';
      return;
    }
    if (!record) {
      setMessage('No offline copy is ready on this device. Open the room online and sign in to prepare one.');
      document.getElementById('room-name').textContent = 'Saved lists';
      document.getElementById('last-saved').textContent = '';
      document.getElementById('lists').replaceChildren();
      return;
    }
    if (slug !== null && record.snapshot.room.slug !== slug) {
      setMessage('No offline copy is ready for this room.');
      document.getElementById('room-name').textContent = 'Saved lists';
      document.getElementById('last-saved').textContent = '';
      document.getElementById('lists').replaceChildren();
      return;
    }

    if (state === 'offline') setMessage('Offline · read only');
    else if (state === 'storage-failure') setMessage('Could not save the latest copy · read only');
    else setMessage('Could not verify the latest copy · read only');
    renderSnapshot(record);
  }

  async function main() {
    if (!storage) {
      setMessage('Offline storage is unavailable in this browser.');
      return;
    }
    const slug = requestedSlug();
    if (slug === undefined) {
      setMessage('No offline copy is available for this address.');
      return;
    }

    let record;
    try {
      record = await storage.readRecord();
    } catch (_) {
      setMessage('Offline storage could not be read on this device.');
      return;
    }

    if (slug === null && !record) {
      setMessage('No offline copy is ready on this device. Open the room online and sign in to prepare one.');
      return;
    }

    let result;
    const checkSlug = slug === null ? record.snapshot.room.slug : slug;
    try {
      result = await refreshOnline(checkSlug);
    } catch (_) {
      result = { kind: 'network-failure' };
    }

    if (result.kind === 'saved') {
      if (slug !== null && result.record.snapshot.room.slug !== slug) {
        setMessage('No offline copy is ready for this room.');
        return;
      }
      setMessage('Online check complete · read only');
      renderSnapshot(result.record);
      return;
    }
    if (result.kind === 'denied') {
      setMessage('Room access could not be confirmed. Return online and sign in again.');
      document.getElementById('room-name').textContent = 'Saved lists';
      document.getElementById('last-saved').textContent = '';
      document.getElementById('lists').replaceChildren();
      return;
    }
    if (result.kind === 'network-failure') {
      await showSavedCopy(slug, 'offline');
      return;
    }
    await showSavedCopy(slug, result.kind);
  }

  let pendingCheck = null;
  function checkRoom() {
    if (pendingCheck) return pendingCheck;
    pendingCheck = main().finally(() => { pendingCheck = null; });
    return pendingCheck;
  }

  checkRoom().catch(() => {
    setMessage('Offline view could not be opened.');
  });
  window.addEventListener('online', () => {
    checkRoom().catch(() => setMessage('Offline view could not be opened.'));
  });
})();
