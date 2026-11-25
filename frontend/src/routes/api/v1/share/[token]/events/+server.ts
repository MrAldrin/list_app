import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiHandler, runApi } from '#lib/server/api.ts';
import { readShareCursor } from '#lib/server/live-cursors.ts';
import { liveStream } from '#lib/server/live-streams.ts';
import type { RequestHandler } from './$types';

const events = API_V1['GET /share/{token}/events'];

export const GET: RequestHandler = apiHandler(({ request, params: { token } }) =>
	liveStream(events, request, (signal) => runApi({ signal }, readShareCursor(token)))
);
