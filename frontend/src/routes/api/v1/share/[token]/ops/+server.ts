import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { OpFields, prepareOp } from '#lib/server/room-ops.ts';
import { submitShareOp } from '#lib/server/share.ts';
import type { RequestHandler } from './$types';

const contract = API_V1['POST /share/{token}/ops'];

export const POST: RequestHandler = apiHandler(async ({ request, params: { token } }) => {
	const prepared = prepareOp(await readApiBody(request, OpFields));
	const { answer } = await runApi(request, submitShareOp(token, prepared));
	return apiSuccess(contract, answer);
});
