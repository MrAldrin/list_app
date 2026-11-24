import { Schema } from 'effect';
import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { requireAdmin } from '#lib/server/admin-session.ts';
import { apiError, apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { revokeInvitation } from '#lib/server/room-invitations.ts';
import type { RequestHandler } from './$types';

const revoke = API_V1['POST /admin/invitations/{invitation_id}/revoke'];
const decodeParams = Schema.decodeUnknownEither(revoke.params);

export const POST: RequestHandler = apiHandler(async (event) => {
	await requireAdmin(event);
	const params = decodeParams(event.params);
	if (params._tag === 'Left') throw apiError(422, 'invalid_request');
	const { request } = event;
	await readApiBody(request, revoke.body);
	await runApi(request, revokeInvitation(params.right.invitation_id));
	return apiSuccess(revoke, {});
});
