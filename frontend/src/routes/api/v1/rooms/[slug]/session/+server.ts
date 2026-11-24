import { API_V1 } from '#lib/contracts/v1/routes.ts';
import {
	ApiError,
	apiError,
	apiHandler,
	apiSuccess,
	readApiBody,
	runApi
} from '#lib/server/api.ts';
import { requireRoomAccess, signInToRoom, signOutOfRoom } from '#lib/server/room-access.ts';
import {
	clearRoomCookie,
	hasRoomCookie,
	roomToken,
	setRoomCookies
} from '#lib/server/room-cookies.ts';
import { RoomSignInLimiter } from '#lib/server/room-sign-in-limiter.ts';
import type { RequestHandler } from './$types';

const signIn = API_V1['POST /rooms/{slug}/session'];
const session = API_V1['GET /rooms/{slug}/session'];
const signOut = API_V1['DELETE /rooms/{slug}/session'];
const limiter = new RoomSignInLimiter();

export const POST: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug }
	} = event;
	const { password } = await readApiBody(request, signIn.body);
	const attempt = limiter.reserve(slug);
	if ('retryAfter' in attempt) {
		throw apiError(429, 'too_many_attempts', undefined, {
			'Retry-After': String(attempt.retryAfter)
		});
	}
	try {
		const { room, token } = await runApi(request, signInToRoom(slug, password));
		attempt.release();
		const response = apiSuccess(signIn, { room });
		setRoomCookies(event, slug, token);
		return response;
	} catch (error) {
		// Only rejected credentials keep the room and global slots for the
		// rest of the window. A temporary database failure gives both back.
		if (error instanceof ApiError && error.code === 'unavailable') attempt.release();
		throw error;
	}
});

export const GET: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug }
	} = event;
	try {
		const { name } = await runApi(request, requireRoomAccess(slug, roomToken(event, slug)));
		return apiSuccess(session, { room: { slug, name } });
	} catch (error) {
		if (
			error instanceof ApiError &&
			error.code === 'not_authenticated' &&
			hasRoomCookie(event, slug)
		) {
			clearRoomCookie(event, slug);
		}
		throw error;
	}
});

export const DELETE: RequestHandler = apiHandler(async (event) => {
	const {
		request,
		params: { slug }
	} = event;
	await runApi(request, signOutOfRoom(slug, roomToken(event, slug)));
	clearRoomCookie(event, slug);
	return apiSuccess(signOut, undefined);
});
