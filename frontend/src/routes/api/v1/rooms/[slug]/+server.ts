import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { deleteRoomWithPassword } from '#lib/server/room-access.ts';
import { clearDeletedRoomCookies, roomToken } from '#lib/server/room-cookies.ts';
import type { RequestHandler } from './$types';

const route = API_V1['DELETE /rooms/{slug}'];

export const DELETE: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug }
	} = event;
	const { password } = await readApiBody(request, route.body);
	await runApi(request, deleteRoomWithPassword(slug, roomToken(event, slug), password));
	clearDeletedRoomCookies(event, slug);
	return apiSuccess(route, undefined);
});
