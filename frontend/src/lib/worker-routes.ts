/**
 * Navigations the app worker must leave to the network.
 *
 * Keep admin, old redirects and non-page addresses off the saved shell.
 */
export function isNetworkOnlyNavigation(pathname: string): boolean {
	return (
		['/admin', '/app', '/static', '/_app', '/room-manifest'].some(
			(prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
		) ||
		[
			'/sw.js',
			'/service-worker.js',
			'/manifest.webmanifest',
			'/manifest.json',
			'/healthz',
			'/favicon.ico',
			'/apple-touch-icon.png',
			'/apple-touch-icon-precomposed.png',
			'/robots.txt'
		].includes(pathname)
	);
}

/** The message a page sends to make the waiting worker take over at once. */
export const SKIP_WAITING = 'skip-waiting';
