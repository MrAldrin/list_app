import { building } from '$app/env';
import type { Handle } from '@sveltejs/kit/hooks';
import {
	apiError,
	apiErrorResponse,
	apiWriteError,
	hasSameOrigin,
	isWriteMethod,
	withApiHeaders
} from '#lib/server/api.ts';

export const handle: Handle = async ({ event, resolve }) => {
	if (import.meta.env.MODE !== 'typescript-server') return resolve(event);

	const path = event.url.pathname;
	if (path !== '/api' && !path.startsWith('/api/')) {
		// The TypeScript build uses our origin check in place of Kit's form guard.
		if (isWriteMethod(event.request.method) && !hasSameOrigin(event)) {
			return new Response('Forbidden', { status: 403 });
		}
		return resolve(event);
	}

	if (event.route.id !== null && isWriteMethod(event.request.method)) {
		const problem = apiWriteError(event);
		if (problem) return withApiHeaders(apiErrorResponse(problem));
	}

	let response = await resolve(event);
	if (response.status === 404 && event.route.id === null) {
		response = apiErrorResponse(apiError(404, 'not_found'));
	}
	if (response.status === 405 && response.headers.has('Allow')) {
		response = apiErrorResponse(apiError(405, 'invalid_request', undefined, response.headers));
	}
	return withApiHeaders(response);
};

export async function init(): Promise<void> {
	if (building || import.meta.env.MODE !== 'typescript-server') return;

	const { checkDatabase, runtime } = await import('#lib/server/runtime.ts');
	await runtime.runPromise(checkDatabase);
	process.once('sveltekit:shutdown', () => void runtime.dispose());
}
