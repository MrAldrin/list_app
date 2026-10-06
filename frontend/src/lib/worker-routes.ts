/**
 * Navigations the app worker must leave to the network.
 *
 * Admin is online-only and never served from the saved shell. The server also
 * redirects the old `/admin/login` and `/app/...` addresses; a saved shell
 * would show them as unknown pages instead.
 */
export function isNetworkOnlyNavigation(pathname: string): boolean {
	return ['/admin', '/app'].some(
		(prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
	);
}
