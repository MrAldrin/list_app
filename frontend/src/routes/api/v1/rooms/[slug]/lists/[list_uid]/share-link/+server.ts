import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { roomToken } from '#lib/server/room-cookies.ts';
import { roomShareLink } from '#lib/server/share.ts';
import type { RequestHandler } from './$types';

const readLink = API_V1['GET /rooms/{slug}/lists/{list_uid}/share-link'];
const resetLink = API_V1['POST /rooms/{slug}/lists/{list_uid}/share-link'];

export const GET: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug, list_uid }
	} = event;
	return apiSuccess(
		readLink,
		await runApi(request, roomShareLink(slug, roomToken(event, slug), list_uid))
	);
});

export const POST: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug, list_uid }
	} = event;
	await readApiBody(request, resetLink.body);
	return apiSuccess(
		resetLink,
		await runApi(request, roomShareLink(slug, roomToken(event, slug), list_uid, true))
	);
});
