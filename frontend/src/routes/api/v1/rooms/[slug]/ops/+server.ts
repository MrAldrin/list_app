import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { roomToken } from '#lib/server/room-cookies.ts';
import { OpFields, prepareOp, submitRoomOp } from '#lib/server/room-ops.ts';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug }
	} = event;
	const prepared = prepareOp(await readApiBody(request, OpFields));
	const { answer } = await runApi(request, submitRoomOp(slug, roomToken(event, slug), prepared));
	return apiSuccess(API_V1['POST /rooms/{slug}/ops'], answer);
});
