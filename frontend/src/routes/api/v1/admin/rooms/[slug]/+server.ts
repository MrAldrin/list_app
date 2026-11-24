import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { deleteAdminRoom } from '#lib/server/admin-rooms.ts';
import { requireAdmin } from '#lib/server/admin-session.ts';
import { apiHandler, apiSuccess, runApi } from '#lib/server/api.ts';
import { clearDeletedRoomCookies } from '#lib/server/room-cookies.ts';
import type { RequestHandler } from './$types';

const remove = API_V1['DELETE /admin/rooms/{slug}'];

export const DELETE: RequestHandler = apiHandler(async (event) => {
	await requireAdmin(event);
	const {
		request,
		params: { slug }
	} = event;
	await runApi(request, deleteAdminRoom(slug));
	clearDeletedRoomCookies(event, slug);
	return apiSuccess(remove, undefined);
});
