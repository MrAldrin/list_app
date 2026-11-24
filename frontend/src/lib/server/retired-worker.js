// Compatibility script for old installs. It does not serve or save responses.
const worker = /** @type {typeof import('$app/service-worker').self} */ (
	/** @type {unknown} */ (self)
);

worker.addEventListener('install', (event) => {
	event.waitUntil(worker.skipWaiting());
});

worker.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			try {
				const names = await caches.keys();
				await Promise.all(names.map((name) => caches.delete(name)));
			} catch {
				// Cache Storage may be unavailable. Still unregister the worker.
			}
			await worker.registration.unregister();
			for (const client of await worker.clients.matchAll({ type: 'window' })) {
				// The navigation can start after the activation has finished.
				void client.navigate(client.url).catch(() => undefined);
			}
		})()
	);
});
