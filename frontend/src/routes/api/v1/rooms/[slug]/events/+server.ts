import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, runApi } from '#lib/server/api.ts';
import { readRoomCursor } from '#lib/server/live-cursors.ts';
import { liveStream } from '#lib/server/live-streams.ts';
import { roomToken } from '#lib/server/room-cookies.ts';
import type { RequestHandler } from './$types';

const events = API_V1['GET /rooms/{slug}/events'];

export const GET: RequestHandler = apiHandler((event) => {
	const {
		request,
		params: { slug }
	} = event;
	const token = roomToken(event, slug);
	return liveStream(events, request, (signal) => runApi({ signal }, readRoomCursor(slug, token)));
});
