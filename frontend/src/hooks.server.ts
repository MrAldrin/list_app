import { building } from '$app/env';
import type { Handle } from '@sveltejs/kit/hooks';
import {
	apiError,
	apiErrorResponse,
	apiWriteError,
	isWriteMethod,
	withApiHeaders
} from '#lib/server/api.ts';
import { browserResponse } from '#lib/server/browser-response.ts';

export const handle: Handle = async ({ event, resolve }) => {
	if (import.meta.env.MODE !== 'typescript-server') return resolve(event);

	const path = event.url.pathname;
	if (path !== '/api' && !path.startsWith('/api/')) {
		return browserResponse(event, resolve);
	}

	if (event.route.id !== null && isWriteMethod(event.request.method)) {
		const problem = apiWriteError(event);
		if (problem) return withApiHeaders(apiErrorResponse(problem));
	}

	let response = await resolve(event);
	if (response.status === 404 && event.route.id === null) {
		response = apiErrorResponse(apiError(404, 'not_found'));
	}
	const allow = response.headers.get('Allow');
	if (response.status === 405 && allow !== null) {
		response = apiErrorResponse(apiError(405, 'invalid_request', undefined, { Allow: allow }));
	}
	return withApiHeaders(response);
};

export async function init(): Promise<void> {
	if (building || import.meta.env.MODE !== 'typescript-server') return;

	const { checkDatabase, runtime } = await import('#lib/server/runtime.ts');
	const { stopLiveStreams } = await import('#lib/server/live-streams.ts');
	await runtime.runPromise(checkDatabase);
	// End long-lived responses as the adapter starts draining requests.
	process.once('SIGTERM', stopLiveStreams);
	process.once('SIGINT', stopLiveStreams);
	process.once('sveltekit:shutdown', () => void runtime.dispose());
}
