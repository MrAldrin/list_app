const LEGACY_WORKER_PATH = '/sw.js';
const SERVICE_WORKER_PATH = '/service-worker.js';

function isLegacyWorker(worker: ServiceWorker | null | undefined): boolean {
	if (!worker) return false;
	try {
		return new URL(worker.scriptURL).pathname === LEGACY_WORKER_PATH;
	} catch {
		return false;
	}
}

/** Register the app worker only after any retired /sw.js worker removes itself. */
export async function registerServiceWorker(
	container: ServiceWorkerContainer | undefined = typeof navigator === 'undefined'
		? undefined
		: navigator.serviceWorker
): Promise<boolean> {
	if (!container) return false;

	try {
		const registrations = await container.getRegistrations();
		const legacyRegistrations = registrations.filter((registration) =>
			[registration.installing, registration.waiting, registration.active].some((worker) =>
				isLegacyWorker(worker)
			)
		);

		if (legacyRegistrations.length > 0 || isLegacyWorker(container.controller)) {
			// The old worker performs cache deletion, unregisters, and reloads its
			// clients. Re-enter on that clean reload instead of racing its cleanup.
			await Promise.all(legacyRegistrations.map((registration) => registration.update()));
			return false;
		}

		// Registering an existing URL also asks the browser to check for an
		// update; cached navigation shells still mount this layout on each load.
		await container.register(SERVICE_WORKER_PATH, { type: 'module' });
		return true;
	} catch {
		// Registration is best-effort. A later page load retries after a network
		// failure, while the current online app remains usable.
		return false;
	}
}
