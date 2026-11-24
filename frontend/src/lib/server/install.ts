import baseManifest from '../../../../src/static/manifest.json';
import appleTouch from '../../../../src/static/icons/apple-touch-icon.png?inline';
import favicon16 from '../../../../src/static/icons/favicon-16.png?inline';
import favicon32 from '../../../../src/static/icons/favicon-32.png?inline';
import icon192 from '../../../../src/static/icons/icon-192.png?inline';
import icon512 from '../../../../src/static/icons/icon-512.png?inline';
import killSwitch from './retired-worker.js?raw';

const icons = new Map(
	[
		['/static/icons/apple-touch-icon.png', appleTouch],
		['/static/icons/favicon-16.png', favicon16],
		['/static/icons/favicon-32.png', favicon32],
		['/static/icons/icon-192.png', icon192],
		['/static/icons/icon-512.png', icon512],
		['/apple-touch-icon.png', appleTouch],
		['/apple-touch-icon-precomposed.png', appleTouch],
		['/favicon.ico', favicon32]
	].map(([path, data]) => [path, Uint8Array.fromBase64(data.split(',')[1])])
);

export function atPath(path: string, prefix: string): boolean {
	return path === prefix || path.startsWith(`${prefix}/`);
}

function manifestStart(path: string): string | undefined {
	if (['/manifest.json', '/manifest.webmanifest', '/static/manifest.json'].includes(path)) {
		return '/';
	}
	const match = /^\/room-manifest\/([^/]+)\.(?:json|webmanifest)$/.exec(path);
	if (!match) return;
	try {
		const slug = decodeURIComponent(match[1]);
		if (slug === '.' || slug === '..') return;
		return `/room/${encodeURIComponent(slug).replace(
			/[!'()*]/g,
			(character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`
		)}`;
	} catch {
		return;
	}
}

export function installResponse(url: URL, method: string): Response | undefined {
	const path = url.pathname;
	const read = method === 'GET' || method === 'HEAD';
	const body = (content: BodyInit, type: string, cache: string) =>
		read
			? new Response(method === 'HEAD' ? null : content, {
					headers: { 'Content-Type': type, 'Cache-Control': cache }
				})
			: new Response(null, { status: 405, headers: { Allow: 'GET, HEAD' } });

	if (path === '/sw.js') return body(killSwitch, 'application/javascript', 'no-store');

	const start = manifestStart(path);
	if (start) {
		return body(
			JSON.stringify({ ...baseManifest, start_url: start }),
			'application/manifest+json',
			'no-cache, no-store, must-revalidate'
		);
	}

	const icon = icons.get(path);
	if (icon) return body(icon, 'image/png', 'no-cache');

	if (atPath(path, '/app') || path === '/admin/login' || path === '/admin/login/') {
		if (!read) return new Response(null, { status: 405, headers: { Allow: 'GET, HEAD' } });
		// A Location beginning // would send the browser to another host.
		const destination = atPath(path, '/app') ? `/${path.slice(4).replace(/^\/+/, '')}` : '/admin';
		return new Response(null, { status: 308, headers: { Location: destination + url.search } });
	}

	if (
		['/static', '/_app', '/room-manifest', '/service-worker.js'].some((prefix) =>
			atPath(path, prefix)
		)
	) {
		return new Response(null, { status: 404 });
	}
}
