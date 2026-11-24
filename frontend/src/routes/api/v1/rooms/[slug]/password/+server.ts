import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess, readApiBody, runApi } from '#lib/server/api.ts';
import { changeRoomPassword } from '#lib/server/room-access.ts';
import { roomToken, setRoomCookies } from '#lib/server/room-cookies.ts';
import { validateNewRoomPassword } from '#lib/server/room-password.ts';
import type { RequestHandler } from './$types';

const route = API_V1['POST /rooms/{slug}/password'];

export const POST: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug }
	} = event;
	const body = await readApiBody(request, route.body);
	validateNewRoomPassword(body.new_password);
	const { room, token } = await runApi(
		request,
		changeRoomPassword(slug, roomToken(event, slug), body.current_password, body.new_password)
	);
	const response = apiSuccess(route, { room });
	setRoomCookies(event, slug, token);
	return response;
});
