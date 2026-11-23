import { json } from '@sveltejs/kit';
import { Schema } from 'effect';
import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { API_VERSION_HEADER, EXPECTED_API_VERSION } from '#lib/contracts/v1/version.ts';
import type { RequestHandler } from './$types';

const route = API_V1['GET /last-room'];
const encodeLastRoom = Schema.encode(route.response);
const cookieName = 'listapp-last-room';

export const GET: RequestHandler = async ({ cookies, request, url }) => {
	if (import.meta.env.MODE !== 'typescript-server') return new Response(null, { status: 404 });

	// This cookie is a navigation hint, not proof of access. Do not look up the room.
	const name = url.protocol === 'https:' ? `__Host-${cookieName}` : cookieName;
	const value = cookies.get(name, { decode: (raw) => raw });
	const slug = value && Array.from(value).length <= 256 ? value : null;
	const { runtime } = await import('#lib/server/runtime.ts');
	const body = await runtime.runPromise(encodeLastRoom({ slug }), { signal: request.signal });
	return json(body, {
		status: route.status,
		headers: { 'Cache-Control': 'no-store', [API_VERSION_HEADER]: String(EXPECTED_API_VERSION) }
	});
};
