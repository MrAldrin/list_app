import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, apiSuccess } from '#lib/server/api.ts';
import { lastRoom } from '#lib/server/room-cookies.ts';
import type { RequestHandler } from './$types';

const route = API_V1['GET /last-room'];

// This cookie is a navigation hint, not proof of access. Do not look up the room.
export const GET: RequestHandler = apiHandler((event) =>
	apiSuccess(route, { slug: lastRoom(event) })
);
