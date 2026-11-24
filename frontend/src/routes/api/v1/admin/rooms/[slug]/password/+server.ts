import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { resetAdminRoomPassword } from '#lib/server/admin-rooms.ts';
import { requireAdmin } from '#lib/server/admin-session.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import type { RequestHandler } from './$types';

const reset = API_V1['POST /admin/rooms/{slug}/password'];

export const POST: RequestHandler = apiHandler(async (event) => {
	await requireAdmin(event);
	const {
		request,
		params: { slug }
	} = event;
	const { new_password } = await readApiBody(request, reset.body);
	await runApi(request, resetAdminRoomPassword(slug, new_password));
	return apiSuccess(reset, {});
});
