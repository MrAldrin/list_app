import { describe, expect, it, vi } from 'vitest';
import { registerServiceWorker } from '#lib/service-worker.ts';

function serviceWorkerContainer(overrides: Partial<ServiceWorkerContainer> = {}) {
	return {
		controller: null,
		getRegistrations: vi.fn().mockResolvedValue([]),
		register: vi.fn().mockResolvedValue({ update: vi.fn().mockResolvedValue(undefined) }),
		...overrides
	} as unknown as ServiceWorkerContainer;
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
