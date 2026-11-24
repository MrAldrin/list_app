import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { requireAdmin } from '#lib/server/admin-session.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { issueInvitation, listInvitations } from '#lib/server/room-invitations.ts';
import type { RequestHandler } from './$types';

const list = API_V1['GET /admin/invitations'];
const issue = API_V1['POST /admin/invitations'];

export const GET: RequestHandler = apiHandler(async (event) => {
	await requireAdmin(event);
	const invitations = await runApi(event.request, listInvitations);
	return apiSuccess(list, { invitations });
});

export const POST: RequestHandler = apiHandler(async (event) => {
	await requireAdmin(event);
	const { request } = event;
	await readApiBody(request, issue.body);
	const issued = await runApi(request, issueInvitation);
	return apiSuccess(issue, issued);
});
