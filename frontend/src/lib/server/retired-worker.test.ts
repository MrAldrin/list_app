import { runInNewContext } from 'node:vm';
import { describe, expect, it, vi } from 'vitest';
import script from './retired-worker.js?raw';

function retiredWorker({ cacheFails }: { cacheFails: boolean }) {
	const handlers = new Map<
		string,
		(event: { waitUntil: (work: Promise<unknown>) => void }) => void
	>();
	const skipWaiting = vi.fn(async () => {});
	const unregister = vi.fn(async () => true);
	const navigate = vi.fn(async () => undefined);
	const matchAll = vi.fn(async () => [{ navigate, url: 'https://example.test/room/home' }]);
	const keys = vi.fn(async () => {
		if (cacheFails) throw new Error('Cache Storage unavailable');
		return ['old-shell'];
	});
	const remove = vi.fn(async () => true);
	runInNewContext(script, {
		caches: { keys, delete: remove },
		self: {
			addEventListener: handlers.set.bind(handlers),
			skipWaiting,
			registration: { unregister },
			clients: { matchAll }
		}
	});

	function dispatch(type: string): Promise<unknown> {
		return new Promise((resolve) => handlers.get(type)?.({ waitUntil: resolve }));
	}
	return { dispatch, handlers, skipWaiting, unregister, navigate, remove };
}

describe('retired worker', () => {
	it.each([false, true])(
		'unregisters and reloads when cache access fails = %s',
		async (cacheFails) => {
			const { dispatch, handlers, skipWaiting, unregister, navigate, remove } = retiredWorker({
				cacheFails
			});
			expect([...handlers.keys()]).toEqual(['install', 'activate']);
			await dispatch('install');
			expect(skipWaiting).toHaveBeenCalledOnce();
			await dispatch('activate');
			if (cacheFails) expect(remove).not.toHaveBeenCalled();
			else expect(remove).toHaveBeenCalledWith('old-shell');
			expect(unregister).toHaveBeenCalledOnce();
			expect(navigate).toHaveBeenCalledWith('https://example.test/room/home');
			expect(unregister).toHaveBeenCalledBefore(navigate);
		}
	);
});
