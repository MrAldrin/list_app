import { version } from '$app/env';
import { assets, immutable, prerendered } from '$app/manifest';
import { resolve } from '$app/paths';
import { self } from '$app/service-worker';
import { isNetworkOnlyNavigation } from './lib/worker-routes';

const CACHE_PREFIX = 'listr-app-shell-';
const CACHE_NAME = `${CACHE_PREFIX}${version}`;
const ORIGIN = self.location.origin;
const APP_SHELL = new URL(resolve('/'), ORIGIN).href;

function isApiPath(pathname: string): boolean {
	return pathname === '/api' || pathname.startsWith('/api/');
}

function isAppAsset(url: URL): boolean {
	return (
		url.origin === ORIGIN &&
		!isApiPath(url.pathname) &&
		url.pathname !== '/sw.js' &&
		url.pathname !== '/service-worker.js'
	);
}

const PRECACHE_URLS = [
	...new Set(
		[...immutable, ...assets, ...prerendered].map(({ path }) => new URL(path, ORIGIN).href)
	)
].filter((href) => isAppAsset(new URL(href)) && href !== APP_SHELL);
const PRECACHE_SET = new Set(PRECACHE_URLS);

async function fetchCompleteResponse(url: string): Promise<Response> {
	const response = await fetch(url, { cache: 'reload' });
	const finalUrl = new URL(response.url || url, ORIGIN);
	if (!response.ok || response.type === 'opaque' || !isAppAsset(finalUrl)) {
		throw new Error(`Could not precache app asset: ${url}`);
	}
	return response;
}

async function discardUnusedVersions(): Promise<void> {
	if (self.registration.installing || self.registration.waiting) return;

	const [windows, controlledWindows] = await Promise.all([
		self.clients.matchAll({ type: 'window', includeUncontrolled: true }),
		self.clients.matchAll({ type: 'window' })
	]);
	const controlledIds = new Set(controlledWindows.map((client) => client.id));
	if (windows.some((client) => !controlledIds.has(client.id))) return;

	const oldCaches = (await caches.keys()).filter(
		(name) => name.startsWith(CACHE_PREFIX) && name !== CACHE_NAME
	);
	await Promise.all(oldCaches.map((name) => caches.delete(name)));
}

async function installCompleteVersion(): Promise<void> {
	const cache = await caches.open(CACHE_NAME);
	try {
		const shell = await fetchCompleteResponse(APP_SHELL);
		await cache.put(APP_SHELL, shell);
		for (const url of PRECACHE_URLS) {
			await cache.put(url, await fetchCompleteResponse(url));
		}
	} catch (error) {
		// A partially staged version is never usable and must not replace the
		// last complete version, which remains in its own versioned cache.
		await caches.delete(CACHE_NAME);
		throw error;
	}
}

self.addEventListener('install', (event) => {
	event.waitUntil(installCompleteVersion());
});

self.addEventListener('activate', (event) => {
	// Keep complete versions if an open page predates worker control. A later
	// fetch can clean them up after those unclaimed clients have closed.
	event.waitUntil(discardUnusedVersions());
});

self.addEventListener('fetch', (event) => {
	const request = event.request;
	if (request.method !== 'GET') return;

	const url = new URL(request.url);
	if (url.origin !== ORIGIN || isApiPath(url.pathname)) return;

	if (request.mode === 'navigate') {
		if (isNetworkOnlyNavigation(url.pathname)) return;
		event.respondWith(
			(async () => {
				await discardUnusedVersions();
				// A controlled page must load the shell from the same version as its
				// cached lazy chunks. A network-first B shell under worker A could
				// request B chunks after the connection disappears.
				const cache = await caches.open(CACHE_NAME);
				return (await cache.match(APP_SHELL)) ?? fetch(request);
			})()
		);
		return;
	}

	if (!PRECACHE_SET.has(url.href)) return;
	event.respondWith(
		(async () => {
			await discardUnusedVersions();
			const cache = await caches.open(CACHE_NAME);
			return (await cache.match(request)) ?? fetch(request);
		})()
	);
});
