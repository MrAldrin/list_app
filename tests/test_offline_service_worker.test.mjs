import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const workerSource = await readFile(new URL('../src/static/sw.js', import.meta.url), 'utf8');

function createWorker(fetchImpl = async () => { throw new TypeError('offline'); }) {
  const listeners = new Map();
  const entries = new Map();
  const cachedAssets = [];
  const cacheNames = new Set();
  const self = {
    location: { origin: 'https://app.example' },
    clients: { claim: async () => {} },
    addEventListener: (name, callback) => listeners.set(name, callback),
  };
  const caches = {
    open: async (name) => {
      cacheNames.add(name);
      return {
        addAll: async (urls) => {
          cachedAssets.push(...urls);
          for (const url of urls) entries.set(url, new Response(`cached:${url}`));
        },
        match: async (request) => {
          const key = typeof request === 'string' ? request : new URL(request.url).pathname;
          return entries.get(key)?.clone();
        },
      };
    },
    keys: async () => [...cacheNames],
    delete: async (name) => cacheNames.delete(name),
  };
  const context = {
    self,
    caches,
    URL,
    Response,
    AbortController,
    setTimeout,
    clearTimeout,
    fetch: fetchImpl,
  };
  vm.runInNewContext(workerSource, context, { filename: 'sw.js' });
  return { listeners, cachedAssets, entries, cacheNames };
}

async function trigger(worker, name, event) {
  worker.listeners.get(name)(event);
  await event.waitUntilPromise;
}

function fetchEvent(url, { method = 'GET', mode = 'navigate' } = {}) {
  return {
    request: { url: `https://app.example${url}`, method, mode },
    respondWith(promise) { this.responsePromise = promise; },
  };
}

test('install caches only the versioned generic shell assets and does not force activation', async () => {
  const worker = createWorker();
  const install = { waitUntil(promise) { this.waitUntilPromise = promise; } };
  await trigger(worker, 'install', install);
  assert.deepEqual(worker.cachedAssets, [
    '/static/offline-shell.html',
    '/static/offline-shell.css',
    '/static/offline-storage.js',
    '/static/offline-shell.js',
  ]);
  assert.deepEqual([...worker.cacheNames], ['listr-offline-shell-v1']);
  assert.doesNotMatch(workerSource, /skipWaiting|cache\.put/);
});

test('activation retires only older shell caches after the new worker activates', async () => {
  const worker = createWorker();
  worker.cacheNames.add('listr-offline-shell-v0');
  worker.cacheNames.add('listr-offline-shell-v1');
  const activation = { waitUntil(promise) { this.waitUntilPromise = promise; } };
  await trigger(worker, 'activate', activation);
  assert.deepEqual([...worker.cacheNames], ['listr-offline-shell-v1']);
});

test('only root and a single room route fall back after network failure', async () => {
  const worker = createWorker();
  const install = { waitUntil(promise) { this.waitUntilPromise = promise; } };
  await trigger(worker, 'install', install);
  for (const path of ['/', '/room/room-1', '/room/room-1/']) {
    const event = fetchEvent(path);
    worker.listeners.get('fetch')(event);
    assert.ok(event.responsePromise, `${path} should use network-first fallback`);
    const response = await event.responsePromise;
    assert.equal(await response.text(), 'cached:/static/offline-shell.html');
  }
});

test('share, private-list, admin, invitation, and nested routes are never shell fallbacks', () => {
  const worker = createWorker();
  for (const path of [
    '/share/public-token',
    '/list/list-slug',
    '/admin',
    '/create-room/invitation',
    '/room/one/two',
    '/room/%2Fsecret',
  ]) {
    const event = fetchEvent(path);
    worker.listeners.get('fetch')(event);
    assert.equal(event.responsePromise, undefined, `${path} must remain network-only`);
  }
});

test('HTTP denial and server errors are returned instead of the shell', async () => {
  for (const status of [401, 403, 404, 503]) {
    const expected = new Response('server response', { status });
    const worker = createWorker(async () => expected);
    const event = fetchEvent('/room/room-1');
    worker.listeners.get('fetch')(event);
    const response = await event.responsePromise;
    assert.equal(response, expected);
    assert.equal(response.status, status);
  }
});

test('only generic shell assets are served from precache', async () => {
  const worker = createWorker();
  const install = { waitUntil(promise) { this.waitUntilPromise = promise; } };
  await trigger(worker, 'install', install);
  const event = fetchEvent('/static/offline-shell.js', { mode: 'no-cors' });
  worker.listeners.get('fetch')(event);
  assert.match(await (await event.responsePromise).text(), /cached:\/static\/offline-shell.js/);
});
