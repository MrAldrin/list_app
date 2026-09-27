const SHELL_CACHE_PREFIX = 'listr-offline-shell-';
const SHELL_CACHE_NAME = `${SHELL_CACHE_PREFIX}v3`;
const SHELL_URL = '/static/offline-shell.html';
const SHELL_ASSETS = [
  SHELL_URL,
  '/static/offline-shell.css',
  '/static/offline-storage.js',
  '/static/offline-shell.js',
];
const NAVIGATION_TIMEOUT_MS = 5000;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name.startsWith(SHELL_CACHE_PREFIX) && name !== SHELL_CACHE_NAME)
          .map((name) => caches.delete(name)),
      ))
      .then(() => self.clients.claim()),
  );
});

function isOfflineShellAsset(url) {
  return url.origin === self.location.origin
    && !url.search
    && SHELL_ASSETS.includes(url.pathname);
}

function isAllowedNavigation(url) {
  if (url.origin !== self.location.origin) return false;
  if (url.pathname === '/') return true;
  const match = /^\/room\/([^/]+)\/?$/.exec(url.pathname);
  if (!match) return false;
  try {
    const slug = decodeURIComponent(match[1]);
    return slug.length > 0 && !slug.includes('/') && !slug.includes('\\');
  } catch (_) {
    return false;
  }
}

async function networkFirstNavigation(request) {
  const controller = new AbortController();
  let timeout;
  try {
    // Safari may not reject an aborted navigation promptly. Race the network so
    // respondWith always receives a document, even when the fetch hangs.
    const deadline = new Promise((_, reject) => {
      timeout = setTimeout(() => {
        controller.abort();
        reject(new Error('Navigation timed out'));
      }, NAVIGATION_TIMEOUT_MS);
    });
    // HTTP denial and server errors are responses, not network failures: return them as-is.
    return await Promise.race([fetch(request, { signal: controller.signal }), deadline]);
  } catch (_) {
    try {
      const cache = await caches.open(SHELL_CACHE_NAME);
      const shell = await cache.match(SHELL_URL);
      if (shell) return shell;
    } catch (_) {
      // Cache storage may be unavailable even after a worker was installed.
    }
    return new Response('<!doctype html><html><meta name="viewport" content="width=device-width, initial-scale=1"><title>ListR offline</title><body><p>Offline view is unavailable on this device. Reopen the room online to prepare it.</p></body></html>', {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  } finally {
    clearTimeout(timeout);
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  if (isOfflineShellAsset(url) && !(request.mode === 'navigate' && url.pathname === SHELL_URL)) {
    event.respondWith(
      caches.open(SHELL_CACHE_NAME)
        .then((cache) => cache.match(request) || fetch(request)),
    );
    return;
  }

  if (request.mode !== 'navigate' || !isAllowedNavigation(url)) return;
  event.respondWith(networkFirstNavigation(request));
});
