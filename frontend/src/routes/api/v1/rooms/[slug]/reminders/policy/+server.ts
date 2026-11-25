import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { reminderAccess } from '#lib/server/reminder-http.ts';
import { getPolicy, putPolicy } from '#lib/server/reminder-policies.ts';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = apiHandler(async (event) => {
	const contract = API_V1['GET /rooms/{slug}/reminders/policy'];
	const access = reminderAccess(event, event.params.slug);
	const response = await runApi(event.request, getPolicy(access, 'room', null));
	return apiSuccess(contract, response);
});

export const PUT: RequestHandler = apiHandler(async (event) => {
	const contract = API_V1['PUT /rooms/{slug}/reminders/policy'];
	const access = reminderAccess(event, event.params.slug);
	const body = await readApiBody(event.request, contract.body);
	const response = await runApi(event.request, putPolicy(access, 'room', null, body));
	return apiSuccess(contract, response);
});
