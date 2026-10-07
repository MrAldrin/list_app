// A tab that still runs an older build can ask for a lazy chunk that a deploy
// replaced. The old file is gone, so the import fails. When that happens the
// page reloads once and gets the new build.
//
// SvelteKit already does this for a failed click on a link: it compares
// `_app/version.json` and opens the link's address with a full page load. This
// covers the first page load, through Vite's `vite:preloadError` event. It
// stops once the app has started, because `reload()` would then open the page
// the user is on, not the one they clicked. See docs/offline-viewing.md.

const STORAGE_KEY = 'listr-stale-build-reload';

/** Time to wait before the reload, so loads in flight can finish. */
const RELOAD_DELAY_MS = 300;

/** A second failure within this time shows the normal error instead of reloading. */
export const RELOAD_WINDOW_MS = 60_000;

type SavedState = Pick<Storage, 'getItem' | 'setItem'>;

/**
 * True when it is fine to reload now. It remembers the time in session storage,
 * so a build that stays broken causes one reload, not a loop. If the storage
 * cannot be used the answer is false: no guard means no reload.
 */
export function mayReloadOnce(storage: SavedState | null, now: number): boolean {
	if (!storage) return false;
	try {
		const last = Number(storage.getItem(STORAGE_KEY));
		if (Number.isFinite(last) && last > 0 && now - last < RELOAD_WINDOW_MS) return false;
		storage.setItem(STORAGE_KEY, String(now));
		return true;
	} catch {
		return false;
	}
}

export interface StaleBuildEnv {
	target: Pick<Window, 'addEventListener' | 'removeEventListener'>;
	storage: SavedState | null;
	isOnline: () => boolean;
	reload: () => void;
	now?: () => number;
}

/** Reloads once when a lazy chunk fails to load. Returns a function that stops it. */
export function installStaleBuildReload(env: StaleBuildEnv): () => void {
	const onPreloadError = () => {
		// Offline, a reload cannot get a newer build; show the normal error.
		if (!env.isOnline()) return;
		if (!mayReloadOnce(env.storage, (env.now ?? Date.now)())) return;
		// The event is not cancelled: the failed import still rejects, so the app
		// shows its error page for the moment until the reload replaces it.
		env.reload();
	};
	env.target.addEventListener('vite:preloadError', onPreloadError);
	return () => env.target.removeEventListener('vite:preloadError', onPreloadError);
}

function sessionStorageOrNull(): SavedState | null {
	try {
		return window.sessionStorage;
	} catch {
		return null;
	}
}

let stopListening: (() => void) | null = null;

/** The browser setup, called from `hooks.client.ts` before the app starts. */
export function startStaleBuildReload(): void {
	stopListening ??= installStaleBuildReload({
		target: window,
		storage: sessionStorageOrNull(),
		isOnline: () => navigator.onLine,
		// A short pause lets requests still in flight finish. WebKit can fail the
		// reloaded page's stylesheets when a reload cancels them.
		reload: () => void setTimeout(() => window.location.reload(), RELOAD_DELAY_MS)
	});
}

/** Called when the app has started: later failures are SvelteKit's to handle. */
export function endStaleBuildReload(): void {
	stopListening?.();
	stopListening = null;
}
