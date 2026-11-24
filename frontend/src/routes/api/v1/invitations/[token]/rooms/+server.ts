import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { createInvitedRoom } from '#lib/server/room-invitations.ts';
import type { RequestHandler } from './$types';

const create = API_V1['POST /invitations/{token}/rooms'];

export const POST: RequestHandler = apiHandler(async ({ request, params: { token } }) => {
	const { name, password } = await readApiBody(request, create.body);
	const room = await runApi(request, createInvitedRoom(token, name, password));
	return apiSuccess(create, { room });
});
