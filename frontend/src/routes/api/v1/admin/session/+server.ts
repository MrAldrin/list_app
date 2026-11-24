import { API_V1 } from '#lib/contracts/v1/routes.ts';
import {
	clearAdminCookie,
	hasAdminCookie,
	requireAdmin,
	setAdminCookie,
	signInAsAdmin
} from '#lib/server/admin-session.ts';
import { ApiError, apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import type { RequestHandler } from './$types';

const signIn = API_V1['POST /admin/session'];
const session = API_V1['GET /admin/session'];
const signOut = API_V1['DELETE /admin/session'];

export const POST: RequestHandler = apiHandler(async (event) => {
	const { request } = event;
	const { password } = await readApiBody(request, signIn.body);
	const token = await runApi(request, signInAsAdmin(password));
	setAdminCookie(event, token);
	return apiSuccess(signIn, {});
});

export const GET: RequestHandler = apiHandler(async (event) => {
	try {
		await requireAdmin(event);
		return apiSuccess(session, {});
	} catch (error) {
		if (error instanceof ApiError && error.code === 'admin_required' && hasAdminCookie(event)) {
			clearAdminCookie(event);
		}
		throw error;
	}
});

export const DELETE: RequestHandler = apiHandler((event) => {
	clearAdminCookie(event);
	return apiSuccess(signOut, undefined);
});
