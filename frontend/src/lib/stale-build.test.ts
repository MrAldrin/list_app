import { describe, expect, it, vi } from 'vitest';
import { installStaleBuildReload, mayReloadOnce, RELOAD_WINDOW_MS } from './stale-build';

function memoryStorage() {
	const data = new Map<string, string>();
	return {
		getItem: (key: string) => data.get(key) ?? null,
		setItem: (key: string, value: string) => void data.set(key, value)
	};
}

describe('mayReloadOnce', () => {
	it('allows the first reload and blocks a second one soon after', () => {
		const storage = memoryStorage();
		expect(mayReloadOnce(storage, 1_000)).toBe(true);
		expect(mayReloadOnce(storage, 1_000 + RELOAD_WINDOW_MS - 1)).toBe(false);
	});

	it('allows another reload after the window has passed', () => {
		const storage = memoryStorage();
		expect(mayReloadOnce(storage, 1_000)).toBe(true);
		expect(mayReloadOnce(storage, 1_000 + RELOAD_WINDOW_MS)).toBe(true);
	});

	it('ignores a damaged saved value', () => {
		const storage = memoryStorage();
		storage.setItem('listr-stale-build-reload', 'not a number');
		expect(mayReloadOnce(storage, 5_000)).toBe(true);
	});

	it('does not reload when storage is missing or throws', () => {
		expect(mayReloadOnce(null, 1_000)).toBe(false);
		const broken = {
			getItem: () => {
				throw new Error('blocked');
			},
			setItem: () => {}
		};
		expect(mayReloadOnce(broken, 1_000)).toBe(false);
	});
});

describe('installStaleBuildReload', () => {
	function setup(online = true) {
		const target = new EventTarget();
		const reload = vi.fn();
		const stop = installStaleBuildReload({
			target,
			storage: memoryStorage(),
			isOnline: () => online,
			reload,
			now: () => 10_000
		});
		const fire = () => {
			const event = new Event('vite:preloadError', { cancelable: true });
			target.dispatchEvent(event);
			return event;
		};
		return { reload, stop, fire };
	}

	it('reloads once, then shows the normal error', () => {
		const { reload, fire } = setup();
		fire();
		expect(reload).toHaveBeenCalledTimes(1);
		// The same failure again: the normal error is shown, no loop.
		fire();
		expect(reload).toHaveBeenCalledTimes(1);
	});

	it('does not reload while offline', () => {
		const { reload, fire } = setup(false);
		fire();
		expect(reload).not.toHaveBeenCalled();
	});

	it('stops listening when asked', () => {
		const { reload, stop, fire } = setup();
		stop();
		fire();
		expect(reload).not.toHaveBeenCalled();
	});
});
