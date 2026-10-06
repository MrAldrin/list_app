// A creation invitation link (/create-room/{token}): anyone with it can
// create a new room (docs/api.md, "Creation invitations"). It never gives
// access to a room; the creator signs in with the new password afterwards.
//
//   import { invitation } from '#lib/data/index.ts';
//   await invitation.active(token);                  // true or false
//   await invitation.createRoom(token, name, pw);    // { ok, result: room }

import { api as defaultApi, type Api } from './api';
import { failed, type ActionResult } from './result';
import { ApiError, type Room } from './types';

type InvitationApi = Pick<Api, 'checkInvitation' | 'createRoomFromInvitation'>;

/** Whether the link can still create a room. Throws for network or server errors. */
export async function active(token: string, client: InvitationApi = defaultApi): Promise<boolean> {
	try {
		await client.checkInvitation(token);
		return true;
	} catch (error) {
		if (isUnavailable(error)) return false;
		throw error;
	}
}

function isUnavailable(error: unknown): boolean {
	return error instanceof ApiError && error.code === 'invitation_unavailable';
}

/** True when an answer means the link can no longer create a room. */
export function isUnavailableResult(result: ActionResult<unknown>): boolean {
	return !result.ok && result.code === 'invitation_unavailable';
}

export async function createRoom(
	token: string,
	name: string,
	password: string,
	client: InvitationApi = defaultApi
): Promise<ActionResult<Room>> {
	try {
		return { ok: true, result: await client.createRoomFromInvitation(token, name, password) };
	} catch (error) {
		return failed(error);
	}
}
