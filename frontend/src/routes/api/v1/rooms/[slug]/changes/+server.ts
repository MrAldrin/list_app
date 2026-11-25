import { Schema } from 'effect';
import { API_V1 } from '#lib/contracts/v1/routes.ts';
import { apiError, apiHandler, apiSuccess, runApi } from '#lib/server/api.ts';
import { roomToken } from '#lib/server/room-cookies.ts';
import { readRoomFeed } from '#lib/server/room-feed.ts';
import type { RequestHandler } from './$types';

const contract = API_V1['GET /rooms/{slug}/changes'];
const decodeQuery = Schema.decodeUnknownEither(contract.query);

export const GET: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		url,
		params: { slug }
	} = event;
	const query = decodeQuery({ since: url.searchParams.getAll('since').at(-1) });
	if (query._tag === 'Left') throw apiError(422, 'invalid_request');
	const feed = await runApi(
		request,
		readRoomFeed(slug, roomToken(event, slug), BigInt(query.right.since))
	);
	return apiSuccess(contract, feed);
});
