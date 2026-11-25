import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { reminderAccess } from '#lib/server/reminder-http.ts';
import { getDevice, patchDevice } from '#lib/server/reminder-preferences.ts';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = apiHandler(async (event) => {
	const contract = API_V1['GET /rooms/{slug}/reminders/preferences/device'];
	const access = reminderAccess(event, event.params.slug);
	const response = await runApi(event.request, getDevice(access));
	return apiSuccess(contract, response);
});

export const PATCH: RequestHandler = apiHandler(async (event) => {
	const contract = API_V1['PATCH /rooms/{slug}/reminders/preferences/device'];
	const access = reminderAccess(event, event.params.slug);
	const body = await readApiBody(event.request, contract.body);
	const response = await runApi(event.request, patchDevice(access, body));
	return apiSuccess(contract, response);
});
