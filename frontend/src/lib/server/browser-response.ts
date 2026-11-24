import { json, type RequestEvent } from '@sveltejs/kit';
import { hasSameOrigin, isWriteMethod } from './api';
import { atPath, installResponse } from './install';

async function healthResponse(request: Request): Promise<Response> {
	if (request.method !== 'GET') {
		return new Response(null, { status: 405, headers: { Allow: 'GET' } });
	}
	const { SqliteClient } = await import('@effect/sql-sqlite-bun');
	const { Effect, Exit } = await import('effect');
	const { runtime } = await import('./runtime');
	const probe = Effect.flatMap(
		SqliteClient.SqliteClient,
		(sql) => sql`SELECT 1 FROM rooms LIMIT 1`
	);
	const ok = Exit.isSuccess(await runtime.runPromiseExit(probe, { signal: request.signal }));
	return json({ ok }, { status: ok ? 200 : 503, headers: { 'Cache-Control': 'no-store' } });
}

export async function browserResponse(
	event: RequestEvent,
	resolve: (event: RequestEvent) => Response | Promise<Response>
): Promise<Response> {
	const { url, request } = event;
	const path = url.pathname;
	let response: Response;
	// The TypeScript build uses our origin check in place of Kit's form guard.
	if (isWriteMethod(request.method) && !hasSameOrigin(event)) {
		response = new Response('Forbidden', { status: 403 });
	} else if (path === '/healthz') {
		response = await healthResponse(request);
	} else {
		response = installResponse(url, request.method) ?? (await resolve(event));
	}

	const headers = new Headers(response.headers);
	if (headers.get('Content-Type')?.startsWith('text/html')) {
		const privatePage =
			path === '/' || ['/room', '/list', '/create-room'].some((prefix) => atPath(path, prefix));
		headers.set('Cache-Control', privatePage ? 'no-store' : 'no-cache');
		headers.set('Referrer-Policy', 'same-origin');
		// Kit's HTML 304 does not retain the referrer policy.
		headers.delete('ETag');
	}
	return new Response(request.method === 'HEAD' ? null : response.body, {
		status: response.status,
		statusText: response.statusText,
		headers
	});
}
