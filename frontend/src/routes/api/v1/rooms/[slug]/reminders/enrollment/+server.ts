import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { reminderAccess, setDeviceCookie } from '#lib/server/reminder-http.ts';
import { enroll } from '#lib/server/reminder-preferences.ts';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = apiHandler(async (event) => {
	const contract = API_V1['POST /rooms/{slug}/reminders/enrollment'];
	const access = reminderAccess(event, event.params.slug);
	const body = await readApiBody(event.request, contract.body);
	const { response, secret } = await runApi(event.request, enroll(access, body));
	if (secret !== null) setDeviceCookie(event, secret);
	return apiSuccess(contract, response);
});
