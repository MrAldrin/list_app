import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { createAdminRoom, listAdminRooms } from '#lib/server/admin-rooms.ts';
import { requireAdmin } from '#lib/server/admin-session.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import type { RequestHandler } from './$types';

const list = API_V1['GET /admin/rooms'];
const create = API_V1['POST /admin/rooms'];

export const GET: RequestHandler = apiHandler(async (event) => {
	await requireAdmin(event);
	const rooms = await runApi(event.request, listAdminRooms);
	return apiSuccess(list, { rooms });
});

export const POST: RequestHandler = apiHandler(async (event) => {
	await requireAdmin(event);
	const { request } = event;
	const { name, password } = await readApiBody(request, create.body);
	const room = await runApi(request, createAdminRoom(name, password));
	return apiSuccess(create, { room });
});
