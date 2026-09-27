(() => {
  'use strict';

  const storage = window.ListROfflineStorage;
  if (!storage) return;

  const REQUEST_TIMEOUT_MS = 5000;
  const DEBOUNCE_MS = 400;
  const MAX_BACKOFF_MS = 60_000;
  const SNAPSHOT_PATH = '/api/offline/rooms/';

  let activeSlug = null;
  let requestTimer = null;
  let retryCount = 0;
  let requestInFlight = null;
  let refreshQueued = false;
  let authorizationRejected = false;
  let eventListenersInstalled = false;

  function routeAllowsSlug(slug) {
    const pathname = window.location.pathname;
    const roomPath = `/room/${encodeURIComponent(slug)}`;
    if (pathname === roomPath || pathname === `${roomPath}/`) return true;
    return /^\/list\/[^/]+\/?$/.test(pathname);
  }

  async function fetchSnapshot(slug) {
    const headers = new Headers({ Accept: 'application/json' });
    try {
      const token = window.localStorage.getItem(`listapp_room_token_${slug}`);
      if (token) headers.set('X-Listapp-Room-Token', token);
    } catch (_) {
      // HTTPS remembered access normally uses the HttpOnly cookie.
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
      const error = new Error('Room authorization was rejected');
      error.definitiveAuthorizationFailure = true;
      throw error;
    }
    if (!response.ok) throw new Error(`Snapshot refresh failed (${response.status})`);
    const snapshot = await response.json();
    if (!storage.validateSnapshot(snapshot, slug)) throw new Error('Snapshot response was invalid');
    return snapshot;
  }

  function ensureStatusElement() {
    let status = document.getElementById('listr-offline-status');
    if (status) return status;
    status = document.createElement('aside');
    status.id = 'listr-offline-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    Object.assign(status.style, {
      position: 'fixed',
      zIndex: '10000',
      left: '12px',
      right: '12px',
      bottom: '12px',
      padding: '10px 14px',
      border: '1px solid #d97706',
      borderRadius: '8px',
      background: '#fffbeb',
      color: '#713f12',
      font: '14px/1.4 system-ui, sans-serif',
      boxShadow: '0 2px 8px #0002',
    });
    document.body.append(status);
    return status;
  }

  function formatTime(record) {
    const time = new Date(record.saved_at);
    return Number.isNaN(time.getTime()) ? 'unknown time' : time.toLocaleString();
  }

  async function showRefreshWarning(slug, message) {
    let detail = '';
    try {
      const record = await storage.readRecord();
      if (!record || record.snapshot.room.slug !== slug) {
        detail = ' No offline copy is ready yet.';
      } else {
        detail = ` Last saved: ${formatTime(record)}.`;
      }
    } catch (_) {
      detail = ' Offline storage could not be checked.';
    }
    if (activeSlug !== slug) return;
    const status = ensureStatusElement();
    status.textContent = `${message}${detail}`;
  }

  function hideWarning() {
    document.getElementById('listr-offline-status')?.remove();
  }

  function addText(parent, tag, text, className) {
    const element = document.createElement(tag);
    element.textContent = text;
    if (className) element.className = className;
    parent.append(element);
    return element;
  }

  async function openOfflineView(slug) {
    if (activeSlug !== slug || document.getElementById('listr-offline-view')) return;
    let record;
    try { record = await storage.readRecord(); } catch (_) { /* Storage unavailable. */ }
    if (activeSlug !== slug || authorizationRejected || navigator.onLine) return;
    if (record?.snapshot.room.slug !== slug) {
      await showRefreshWarning(slug, 'No offline copy is ready on this device.');
      return;
    }
    const overlay = document.createElement('div');
    overlay.id = 'listr-offline-view';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', 'Read-only offline view');
    Object.assign(overlay.style, {
      position: 'fixed', inset: '0', zIndex: '10001', overflowY: 'auto',
    });
    // Keep the CSS inside this dialog: loading the shell stylesheet globally
    // would override NiceGUI's online page underneath it.
    const shadow = overlay.attachShadow({ mode: 'open' });
    const stylesheet = document.createElement('link');
    stylesheet.rel = 'stylesheet';
    stylesheet.href = '/static/offline-shell.css';
    shadow.append(stylesheet);
    const app = addText(shadow, 'div', '', 'app offline-view');
    let dark = false;
    try { dark = localStorage.getItem('listapp_theme') === 'dark'; } catch (_) { /* Optional preference. */ }
    function applyTheme() {
      app.classList.toggle('dark', dark);
      overlay.style.background = dark ? '#121212' : '#f5f7fa';
    }
    applyTheme();
    const header = addText(app, 'header', '', 'app-header');
    const logo = addText(header, 'span', '', 'logo');
    logo.setAttribute('aria-label', 'ListR');
    addText(logo, 'strong', 'List');
    addText(logo, 'strong', 'R');
    const title = addText(header, 'h1', record.snapshot.room.name);
    const theme = addText(header, 'button', '◐', 'theme-toggle');
    theme.type = 'button';
    theme.setAttribute('aria-label', 'Toggle light and dark theme');
    theme.addEventListener('click', () => {
      dark = !dark;
      applyTheme();
      try { localStorage.setItem('listapp_theme', dark ? 'dark' : 'light'); } catch (_) { /* Optional preference. */ }
    });
    const close = addText(header, 'button', '×', 'theme-toggle');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close offline view');
    close.addEventListener('click', () => overlay.remove());
    const content = addText(app, 'main', '');
    const notice = addText(content, 'div', '', 'notice');
    notice.setAttribute('role', 'status');
    addText(notice, 'span', '◌', 'signal').setAttribute('aria-hidden', 'true');
    const message = addText(notice, 'div', '');
    addText(message, 'p', 'Offline · read only').id = 'status';
    addText(message, 'p', `Last saved: ${formatTime(record)}`).id = 'last-saved';
    const lists = addText(content, 'section', '');
    lists.setAttribute('aria-label', 'Saved lists');

    function renderList(index) {
      const list = record.snapshot.lists[index];
      if (!list) return;
      title.textContent = list.name;
      lists.replaceChildren();
      const back = addText(lists, 'button', '‹  Back to room', 'back');
      back.type = 'button';
      back.addEventListener('click', renderRoom);
      addText(lists, 'p', `${list.items.length} ${list.items.length === 1 ? 'item' : 'items'} · saved copy`, 'section-title');
      if (list.list_tags.length) addText(lists, 'p', `Tags: ${list.list_tags.join(', ')}`, 'item-details');
      if (!list.items.length) addText(lists, 'p', 'No items in this list when it was last saved.', 'empty');
      else {
        const items = addText(lists, 'ul', '', 'items');
        items.setAttribute('aria-label', 'Saved items, read only');
        for (const item of list.items) {
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
    function renderRoom() {
      title.textContent = record.snapshot.room.name;
      lists.replaceChildren();
      addText(lists, 'p', 'Your saved lists', 'section-title');
      for (const [index, list] of record.snapshot.lists.entries()) {
        const button = addText(lists, 'button', '', 'list-link');
        button.type = 'button';
        addText(button, 'span', '☷', 'list-icon').setAttribute('aria-hidden', 'true');
        const label = addText(button, 'span', '', 'list-text');
        addText(label, 'strong', list.name);
        addText(label, 'small', `${list.items.length} ${list.items.length === 1 ? 'item' : 'items'}`);
        addText(button, 'span', '›', 'chevron').setAttribute('aria-hidden', 'true');
        button.addEventListener('click', () => renderList(index));
      }
      if (!record.snapshot.lists.length) addText(lists, 'p', 'No lists in the last saved copy.', 'empty');
      addText(lists, 'p', 'Open the room online to edit or refresh your lists.', 'footnote');
    }
    renderRoom();
    document.body.append(overlay);
  }

  async function showOfflineLink() {
    const slug = activeSlug;
    if (!slug || !routeAllowsSlug(slug)) return;
    let record;
    try { record = await storage.readRecord(); } catch (_) { /* Storage unavailable. */ }
    const ready = record?.snapshot.room.slug === slug;
    if (activeSlug !== slug || navigator.onLine) return;
    if (!ready) {
      await showRefreshWarning(slug, 'Offline view is not ready on this device. Reopen the room online.');
      return;
    }
    const status = ensureStatusElement();
    status.replaceChildren();
    const message = document.createElement('span');
    message.textContent = 'Connection lost. ';
    const link = document.createElement('a');
    link.href = `/room/${encodeURIComponent(slug)}`;
    link.textContent = 'Open the read-only offline view';
    link.style.color = 'inherit';
    link.style.fontWeight = '700';
    link.addEventListener('click', (event) => {
      event.preventDefault();
      openOfflineView(slug);
    });
    status.append(message, link);
  }

  function retryDelay() {
    return Math.min(1000 * (2 ** Math.max(0, retryCount - 1)), MAX_BACKOFF_MS);
  }

  function scheduleRefresh(delay = DEBOUNCE_MS) {
    if (!activeSlug || !routeAllowsSlug(activeSlug) || authorizationRejected || document.visibilityState !== 'visible') return;
    window.clearTimeout(requestTimer);
    requestTimer = window.setTimeout(() => {
      requestTimer = null;
      refresh();
    }, Math.max(delay, retryCount ? retryDelay() : 0));
  }

  async function refresh() {
    if (!activeSlug || !routeAllowsSlug(activeSlug) || authorizationRejected || document.visibilityState !== 'visible') return false;
    if (requestInFlight) {
      refreshQueued = true;
      return requestInFlight;
    }

    const requestedSlug = activeSlug;
    requestInFlight = (async () => {
      try {
        const snapshot = await fetchSnapshot(requestedSlug);
        if (activeSlug !== requestedSlug) return false;
        await storage.saveRecord(snapshot);
        retryCount = 0;
        hideWarning();
        document.getElementById('listr-offline-view')?.remove();
        return true;
      } catch (error) {
        if (error.definitiveAuthorizationFailure) {
          document.getElementById('listr-offline-view')?.remove();
          try {
            await storage.clearRecordForRoom(requestedSlug);
            await showRefreshWarning(requestedSlug, 'Room access was rejected; the offline copy was removed.');
          } catch (_) {
            await showRefreshWarning(requestedSlug, 'Room access was rejected, but this device could not clear its offline copy.');
          }
          if (activeSlug === requestedSlug) authorizationRejected = true;
          return false;
        }
        if (activeSlug !== requestedSlug) return false;
        retryCount += 1;
        await showRefreshWarning(requestedSlug, 'The offline copy could not be updated.');
        if (!navigator.onLine) await showOfflineLink();
        scheduleRefresh(retryDelay());
        return false;
      } finally {
        requestInFlight = null;
        if (refreshQueued) {
          refreshQueued = false;
          scheduleRefresh();
        }
      }
    })();
    return requestInFlight;
  }

  function start(slug) {
    if (typeof slug !== 'string' || !slug || !routeAllowsSlug(slug)) return false;
    if (activeSlug !== slug) {
      activeSlug = slug;
      retryCount = 0;
      authorizationRejected = false;
      window.clearTimeout(requestTimer);
    }
    if (!eventListenersInstalled) {
      window.addEventListener('online', () => scheduleRefresh());
      window.addEventListener('offline', showOfflineLink);
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') scheduleRefresh();
      });
      eventListenersInstalled = true;
    }
    if (!navigator.onLine) showOfflineLink();
    scheduleRefresh(0);
    return true;
  }

  window.ListROffline = {
    start,
    refresh: () => scheduleRefresh(),
    clear: () => activeSlug ? storage.clearRecordForRoom(activeSlug) : Promise.resolve(false),
    stop: () => {
      activeSlug = null;
      authorizationRejected = true;
      refreshQueued = false;
      window.clearTimeout(requestTimer);
      hideWarning();
      document.getElementById('listr-offline-view')?.remove();
    },
  };

  const initialSlug = document.currentScript?.dataset.roomSlug;
  if (initialSlug) start(initialSlug);
})();
