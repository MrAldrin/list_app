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

  function showOfflineLink() {
    if (!activeSlug || !routeAllowsSlug(activeSlug)) return;
    const status = ensureStatusElement();
    status.replaceChildren();
    const message = document.createElement('span');
    message.textContent = 'Connection lost. ';
    const link = document.createElement('a');
    link.href = `/room/${encodeURIComponent(activeSlug)}`;
    link.textContent = 'Open the read-only offline view';
    link.style.color = 'inherit';
    link.style.fontWeight = '700';
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
        return true;
      } catch (error) {
        if (error.definitiveAuthorizationFailure) {
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
    },
  };

  const initialSlug = document.currentScript?.dataset.roomSlug;
  if (initialSlug) start(initialSlug);
})();
