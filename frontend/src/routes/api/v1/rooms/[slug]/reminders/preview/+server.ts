import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { reminderAccess } from '#lib/server/reminder-http.ts';
import { previewReminder } from '#lib/server/reminder-preview.ts';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = apiHandler(async (event) => {
	const contract = API_V1['POST /rooms/{slug}/reminders/preview'];
	const access = reminderAccess(event, event.params.slug);
	const body = await readApiBody(event.request, contract.body);
	const response = await runApi(event.request, previewReminder(access, body));
	return apiSuccess(contract, response);
});
