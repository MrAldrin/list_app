const SHELL_CACHE_PREFIX = 'listr-offline-shell-';
const SHELL_CACHE_NAME = `${SHELL_CACHE_PREFIX}v1`;
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
  const timeout = setTimeout(() => controller.abort(), NAVIGATION_TIMEOUT_MS);
  try {
    // HTTP denial and server errors are responses, not network failures: return them as-is.
    return await fetch(request, { signal: controller.signal });
  } catch (_) {
    const cache = await caches.open(SHELL_CACHE_NAME);
    return (await cache.match(SHELL_URL)) || Response.error();
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
