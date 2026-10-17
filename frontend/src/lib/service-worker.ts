// New app versions (docs/offline-viewing.md, "New versions"): the browser
// downloads a new worker in the background, but it waits until every page of
// the old one is closed. On a phone that can take days. So a page that opens,
// or comes back to the screen, while a new version waits asks it to take over
// at once. Every open page then reloads onto it, unless that page holds unsent
// changes or typed text. Coming back also checks for a newer version; it
// downloads in the background and takes over on the next return.

import { compat } from '#lib/data/compat.svelte.ts';
import { SKIP_WAITING } from '#lib/worker-routes.ts';

const LEGACY_WORKER_PATH = '/sw.js';
const SERVICE_WORKER_PATH = '/service-worker.js';

/** How long the Reload button waits for a new version to download or start. */
export const UPDATE_WAIT_MS = 10_000;

export interface VersionSwitchOptions {
	/** Unsent changes: the takeover waits until they are sent. */
	hasWaitingWrites?: () => boolean;
	/** Text typed into a field but not submitted yet; a reload would lose it. */
	hasTypedText?: () => boolean;
	reload?: () => void;
	/** Where "the app came back to the screen" is heard. */
	visibility?: Pick<Document, 'addEventListener' | 'visibilityState'>;
}

function defaultContainer(): ServiceWorkerContainer | undefined {
	return typeof navigator === 'undefined' ? undefined : navigator.serviceWorker;
}

function hasTypedText(): boolean {
	return [...document.querySelectorAll('input, textarea')].some(
		(field) =>
			(field instanceof HTMLTextAreaElement ||
				(field instanceof HTMLInputElement && ['text', 'search', ''].includes(field.type))) &&
			field.value.trim() !== ''
	);
}

const defaults: Omit<Required<VersionSwitchOptions>, 'visibility'> = {
	hasWaitingWrites: () => compat.waitingWrites > 0,
	hasTypedText,
	reload: () => window.location.reload()
};

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
	container: ServiceWorkerContainer | undefined = defaultContainer(),
	options: VersionSwitchOptions = {}
): Promise<boolean> {
	if (!container) return false;
	const { hasWaitingWrites, hasTypedText, reload, visibility } = {
		...defaults,
		visibility: typeof document === 'undefined' ? undefined : document,
		...options
	};
	const busy = () => hasWaitingWrites() || hasTypedText();
	const switchTo = (waiting: ServiceWorker | null | undefined) => {
		if (waiting && !busy()) waiting.postMessage({ type: SKIP_WAITING });
	};

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

		// The worker never claims pages, so this only fires when a waiting
		// version was told to take over: by this page, another tab or Reload.
		container.addEventListener('controllerchange', () => {
			if (!busy()) reload();
		});
		// Before registering: offline, register() fails on its update check.
		switchTo(registrations.find((registration) => registration.waiting)?.waiting);

		// A phone keeps the app in memory, so coming back is often its only
		// "open". Switch to a waiting version, or look for a newer one.
		visibility?.addEventListener('visibilitychange', () => {
			if (visibility.visibilityState !== 'visible') return;
			void container
				.getRegistration()
				.then((registration) => {
					if (registration?.waiting) switchTo(registration.waiting);
					else return registration?.update();
				})
				.catch(() => undefined);
		});

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

function waitForState(
	worker: ServiceWorker,
	states: ServiceWorkerState[],
	ms: number
): Promise<boolean> {
	return new Promise((resolve) => {
		if (states.includes(worker.state)) return resolve(true);
		const timer = setTimeout(() => finish(false), ms);
		function finish(reached: boolean) {
			clearTimeout(timer);
			worker.removeEventListener('statechange', onChange);
			resolve(reached);
		}
		function onChange() {
			if (states.includes(worker.state)) finish(true);
			else if (worker.state === 'redundant') finish(false);
		}
		worker.addEventListener('statechange', onChange);
	});
}

/**
 * The update notice's Reload button. A plain reload could load the old saved
 * version again, so first fetch the newest version, let it take over, then
 * reload. Offline, or when there is no new version, it just reloads. The
 * notice has already said what a reload does to unsent changes, so it reloads anyway.
 */
export async function reloadOntoNewVersion(
	container: ServiceWorkerContainer | undefined = defaultContainer(),
	reload: () => void = defaults.reload,
	waitMs = UPDATE_WAIT_MS
): Promise<void> {
	try {
		const registration = await container?.getRegistration();
		if (registration) {
			await Promise.race([
				registration.update().catch(() => undefined),
				new Promise((resolve) => setTimeout(resolve, waitMs))
			]);
			const installing = registration.installing;
			if (!registration.waiting && installing) {
				await waitForState(installing, ['installed', 'activating', 'activated'], waitMs);
			}
			const waiting = registration.waiting;
			if (waiting) {
				waiting.postMessage({ type: SKIP_WAITING });
				await waitForState(waiting, ['activated'], waitMs);
			}
		}
	} catch {
		// Nothing here may keep the button from reloading.
	}
	reload();
}
