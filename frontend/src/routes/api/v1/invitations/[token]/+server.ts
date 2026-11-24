import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, runApi } from '#lib/server/api.ts';
import { checkInvitation } from '#lib/server/room-invitations.ts';
import type { RequestHandler } from './$types';

const check = API_V1['GET /invitations/{token}'];

export const GET: RequestHandler = apiHandler(async ({ request, params: { token } }) => {
	await runApi(request, checkInvitation(token));
	return apiSuccess(check, {});
});
