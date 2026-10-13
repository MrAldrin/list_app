import { describe, expect, it, vi } from 'vitest';
import { reloadOntoNewVersion, registerServiceWorker } from '#lib/service-worker.ts';

/** A worker whose state the test moves on, like the browser would. */
function fakeWorker(state: ServiceWorkerState) {
	const target = new EventTarget();
	const worker = {
		state,
		scriptURL: 'https://list.test/service-worker.js',
		postMessage: vi.fn(),
		addEventListener: target.addEventListener.bind(target),
		removeEventListener: target.removeEventListener.bind(target),
		moveTo(next: ServiceWorkerState) {
			worker.state = next;
			target.dispatchEvent(new Event('statechange'));
		}
	};
	return worker;
}

function serviceWorkerContainer(overrides: Partial<ServiceWorkerContainer> = {}) {
	const target = new EventTarget();
	return {
		controller: null,
		getRegistrations: vi.fn().mockResolvedValue([]),
		register: vi.fn().mockResolvedValue({ waiting: null }),
		addEventListener: target.addEventListener.bind(target),
		changeController: () => target.dispatchEvent(new Event('controllerchange')),
		...overrides
	} as unknown as ServiceWorkerContainer & { changeController(): void };
}

describe('registerServiceWorker', () => {
	it('registers the explicit SvelteKit worker URL as a module', async () => {
		const container = serviceWorkerContainer();

		expect(await registerServiceWorker(container)).toBe(true);
		expect(container.register).toHaveBeenCalledWith('/service-worker.js', {
			type: 'module'
		});
	});

	it('waits for the old worker update and leaves new registration to its reload', async () => {
		const legacy = {
			active: { scriptURL: 'https://list.test/sw.js?old=1' } as ServiceWorker,
			installing: null,
			waiting: null,
			update: vi.fn().mockResolvedValue(undefined)
		} as unknown as ServiceWorkerRegistration;
		const container = serviceWorkerContainer({
			getRegistrations: vi.fn().mockResolvedValue([legacy])
		});

		expect(await registerServiceWorker(container)).toBe(false);
		expect(legacy.update).toHaveBeenCalledOnce();
		expect(container.register).not.toHaveBeenCalled();
	});

	it('does not register while the current page is still controlled by /sw.js', async () => {
		const container = serviceWorkerContainer({
			controller: { scriptURL: 'https://list.test/sw.js' } as ServiceWorker
		});

		expect(await registerServiceWorker(container)).toBe(false);
		expect(container.register).not.toHaveBeenCalled();
	});

	it('does not throw when service workers are unavailable or registration fails', async () => {
		await expect(registerServiceWorker(undefined)).resolves.toBe(false);
		const container = serviceWorkerContainer({
			register: vi.fn().mockRejectedValue(new Error('offline'))
		});

		await expect(registerServiceWorker(container)).resolves.toBe(false);
	});
});

describe('switching to a waiting version on open', () => {
	const SKIP = { type: 'skip-waiting' };

	it('asks a waiting version to take over, then reloads when it does', async () => {
		const waiting = fakeWorker('installed');
		const container = serviceWorkerContainer({
			getRegistrations: vi.fn().mockResolvedValue([{ waiting }])
		});
		const reload = vi.fn();

		await registerServiceWorker(container, { hasWaitingWrites: () => false, reload });
		expect(waiting.postMessage).toHaveBeenCalledWith(SKIP);
		expect(reload).not.toHaveBeenCalled();

		container.changeController();
		expect(reload).toHaveBeenCalledOnce();
	});

	it('does nothing when no version waits', async () => {
		const container = serviceWorkerContainer();
		const reload = vi.fn();

		await registerServiceWorker(container, { hasWaitingWrites: () => false, reload });
		expect(reload).not.toHaveBeenCalled();
	});

	it('keeps the old version while changes wait to be sent', async () => {
		const waiting = fakeWorker('installed');
		const container = serviceWorkerContainer({
			getRegistrations: vi.fn().mockResolvedValue([{ waiting }])
		});
		const reload = vi.fn();

		await registerServiceWorker(container, { hasWaitingWrites: () => true, reload });
		expect(waiting.postMessage).not.toHaveBeenCalled();
	});

	it('does not reload a tab with unsent changes when another tab switches', async () => {
		const container = serviceWorkerContainer();
		const reload = vi.fn();
		let unsent = true;

		await registerServiceWorker(container, { hasWaitingWrites: () => unsent, reload });
		container.changeController();
		expect(reload).not.toHaveBeenCalled();

		unsent = false;
		container.changeController();
		expect(reload).toHaveBeenCalledOnce();
	});
});

describe('reloadOntoNewVersion', () => {
	function containerWith(registration: Partial<ServiceWorkerRegistration> | undefined) {
		return serviceWorkerContainer({
			getRegistration: vi.fn().mockResolvedValue(registration)
		});
	}

	it('lets a waiting version take over before reloading', async () => {
		const waiting = fakeWorker('installed');
		const reload = vi.fn();
		const registration = {
			waiting,
			installing: null,
			update: vi.fn().mockResolvedValue(undefined)
		} as unknown as ServiceWorkerRegistration;
		waiting.postMessage.mockImplementation(() => waiting.moveTo('activated'));

		await reloadOntoNewVersion(containerWith(registration), reload, 1_000);
		expect(waiting.postMessage).toHaveBeenCalledWith({ type: 'skip-waiting' });
		expect(reload).toHaveBeenCalledOnce();
	});

	it('waits for a new version that is still downloading', async () => {
		const worker = fakeWorker('installing');
		const reload = vi.fn();
		const registration = {
			waiting: null as unknown,
			installing: null as unknown,
			update: vi.fn(async () => {
				registration.installing = worker;
				setTimeout(() => {
					registration.installing = null;
					registration.waiting = worker;
					worker.moveTo('installed');
				}, 10);
			})
		};
		worker.postMessage.mockImplementation(() => worker.moveTo('activated'));

		await reloadOntoNewVersion(
			containerWith(registration as unknown as ServiceWorkerRegistration),
			reload,
			1_000
		);
		expect(worker.postMessage).toHaveBeenCalledOnce();
		expect(reload).toHaveBeenCalledOnce();
	});

	it('just reloads offline or without a worker', async () => {
		const reload = vi.fn();
		const offline = {
			waiting: null,
			installing: null,
			update: vi.fn().mockRejectedValue(new Error('offline'))
		} as unknown as ServiceWorkerRegistration;

		await reloadOntoNewVersion(containerWith(offline), reload, 1_000);
		await reloadOntoNewVersion(containerWith(undefined), reload, 1_000);
		await reloadOntoNewVersion(undefined, reload, 1_000);
		expect(reload).toHaveBeenCalledTimes(3);
	});

	it('still reloads when the new version never starts', async () => {
		const waiting = fakeWorker('installed');
		const reload = vi.fn();
		const registration = {
			waiting,
			installing: null,
			update: vi.fn().mockResolvedValue(undefined)
		} as unknown as ServiceWorkerRegistration;

		await reloadOntoNewVersion(containerWith(registration), reload, 20);
		expect(reload).toHaveBeenCalledOnce();
	});
});
