(() => {
  'use strict';

  const storage = window.ListROfflineStorage;
  const REQUEST_TIMEOUT_MS = 5000;
  const SNAPSHOT_PATH = '/api/offline/rooms/';
  let selectedList = null;
  let currentRecord = null;

  document.getElementById('theme-toggle').addEventListener('click', () => {
    const dark = document.documentElement.classList.toggle('dark');
    try { window.localStorage.setItem('listapp_theme', dark ? 'dark' : 'light'); } catch (_) { /* Optional preference. */ }
  });

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

  function clearView() {
    selectedList = null;
    currentRecord = null;
    document.getElementById('room-name').textContent = 'Saved lists';
    document.getElementById('last-saved').textContent = '';
    document.getElementById('lists').replaceChildren();
  }

  function renderSnapshot(record) {
    if (currentRecord && currentRecord.snapshot.room.slug !== record.snapshot.room.slug) selectedList = null;
    currentRecord = record;
    const snapshot = record.snapshot;
    const lists = document.getElementById('lists');
    lists.replaceChildren();
    showLastSaved(record);
    // Lists have no stable ID in the snapshot. If the selected position changed,
    // return to the room rather than accidentally displaying a different list.
    if (selectedList !== null && snapshot.lists[selectedList.index]?.name !== selectedList.name) {
      selectedList = null;
    }
    const active = selectedList === null ? null : snapshot.lists[selectedList.index];
    document.getElementById('room-name').textContent = active ? active.name : snapshot.room.name;
    if (!active) {
      addText(lists, 'p', 'Your saved lists', 'section-title');
      for (const [index, list] of snapshot.lists.entries()) {
        const button = addText(lists, 'button', '', 'list-link');
        button.type = 'button';
        addText(button, 'span', '☷', 'list-icon').setAttribute('aria-hidden', 'true');
        const label = addText(button, 'span', '', 'list-text');
        addText(label, 'strong', list.name);
        addText(label, 'small', `${list.items.length} ${list.items.length === 1 ? 'item' : 'items'}`);
        addText(button, 'span', '›', 'chevron').setAttribute('aria-hidden', 'true');
        button.addEventListener('click', () => {
          selectedList = { index, name: list.name };
          renderSnapshot(currentRecord);
        });
      }
      if (!snapshot.lists.length) addText(lists, 'p', 'No lists in the last saved copy.', 'empty');
      addText(lists, 'p', 'Open the room online to edit or refresh your lists.', 'footnote');
      return;
    }

    const back = addText(lists, 'button', '‹  Back to room', 'back');
    back.type = 'button';
    back.addEventListener('click', () => { selectedList = null; renderSnapshot(currentRecord); });
    addText(lists, 'p', `${active.items.length} ${active.items.length === 1 ? 'item' : 'items'} · saved copy`, 'section-title');
    if (active.list_tags.length) addText(lists, 'p', `Tags: ${active.list_tags.join(', ')}`, 'item-details');
    if (!active.items.length) addText(lists, 'p', 'No items in this list when it was last saved.', 'empty');
    else {
      const items = addText(lists, 'ul', '', 'items');
      items.setAttribute('aria-label', 'Saved items, read only');
      for (const item of active.items) {
        const row = addText(items, 'li', '', item.done ? 'done' : '');
        row.setAttribute('aria-label', `${item.name}, ${item.done ? 'checked' : 'not checked'}, quantity ${item.quantity}`);
        addText(row, 'span', item.done ? '✓' : '', 'check').setAttribute('aria-hidden', 'true');
        const info = addText(row, 'div', '', 'item-info');
        addText(info, 'span', item.name, 'item-name');
        if (item.description) addText(info, 'span', item.description, 'item-details');
        for (const tag of item.active_tags) addText(info, 'span', `Tags: ${tag}`, 'tag');
        addText(row, 'span', `× ${item.quantity}`, 'quantity');
      }
    }
    addText(lists, 'p', 'Read only while offline. Reconnect to make changes.', 'footnote');
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
      clearView();
      return;
    }
    if (!record) {
      setMessage('No offline copy is ready on this device. Open the room online and sign in to prepare one.');
      clearView();
      return;
    }
    if (slug !== null && record.snapshot.room.slug !== slug) {
      setMessage('No offline copy is ready for this room.');
      clearView();
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
      clearView();
      return;
    }
    const slug = requestedSlug();
    if (slug === undefined) {
      setMessage('No offline copy is available for this address.');
      clearView();
      return;
    }

    let record;
    try {
      record = await storage.readRecord();
    } catch (_) {
      setMessage('Offline storage could not be read on this device.');
      clearView();
      return;
    }

    if (slug === null && !record) {
      setMessage('No offline copy is ready on this device. Open the room online and sign in to prepare one.');
      clearView();
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
        clearView();
        return;
      }
      setMessage('Online check complete · read only');
      renderSnapshot(result.record);
      return;
    }
    if (result.kind === 'denied') {
      setMessage('Room access could not be confirmed. Return online and sign in again.');
      clearView();
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
