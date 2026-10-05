// Admin: sign in with the app password, see every room, create a room,
// reset a room password and manage creation invitations (docs/api.md,
// "Admin" and "Creation invitations"). Admin sign-in never gives
// room access; opening a room still needs its password.
//
//   import { admin } from '#lib/data/index.ts';
//   await admin.login(password);   // { ok } or { ok: false, message }

import { api as defaultApi, type Api } from './api';
import { failed, type ActionResult } from './result';
import { ApiError, type Invitation, type IssuedInvitation, type Room } from './types';

type AdminApi = Pick<
	Api,
	| 'adminLogin'
	| 'adminSession'
	| 'adminLogout'
	| 'adminRooms'
	| 'adminCreateRoom'
	| 'adminResetPassword'
	| 'adminInvitations'
	| 'adminIssueInvitation'
	| 'adminRevokeInvitation'
>;

async function attempt<R>(request: () => Promise<R>): Promise<ActionResult<R>> {
	try {
		return { ok: true, result: await request() };
	} catch (error) {
		return failed(error);
	}
}

/** True when an answer means "not signed in as admin" (for example, signed out in another tab). */
export function isSignedOut(result: ActionResult<unknown>): boolean {
	return !result.ok && result.code === 'admin_required';
}

export function login(
	password: string,
	client: AdminApi = defaultApi
): Promise<ActionResult<void>> {
	return attempt(() => client.adminLogin(password));
}

export function logout(client: AdminApi = defaultApi): Promise<ActionResult<void>> {
	return attempt(() => client.adminLogout());
}

/** Whether this browser is signed in as admin. Throws for network or server errors. */
export async function signedIn(client: AdminApi = defaultApi): Promise<boolean> {
	try {
		await client.adminSession();
		return true;
	} catch (error) {
		if (error instanceof ApiError && error.status === 401) return false;
		throw error;
	}
}

export function rooms(client: AdminApi = defaultApi): Promise<ActionResult<Room[]>> {
	return attempt(() => client.adminRooms());
}

export function createRoom(
	name: string,
	password: string,
	client: AdminApi = defaultApi
): Promise<ActionResult<Room>> {
	return attempt(() => client.adminCreateRoom(name, password));
}

export function resetPassword(
	slug: string,
	newPassword: string,
	client: AdminApi = defaultApi
): Promise<ActionResult<void>> {
	return attempt(() => client.adminResetPassword(slug, newPassword));
}

export function invitations(client: AdminApi = defaultApi): Promise<ActionResult<Invitation[]>> {
	return attempt(() => client.adminInvitations());
}

/** Issues a 7-day invitation. Show its link now: the token is never sent again. */
export function issueInvitation(
	client: AdminApi = defaultApi
): Promise<ActionResult<IssuedInvitation>> {
	return attempt(() => client.adminIssueInvitation());
}

/** Stops further room creation with this invitation; rooms made with it stay. */
export function revokeInvitation(
	id: number,
	client: AdminApi = defaultApi
): Promise<ActionResult<void>> {
	return attempt(() => client.adminRevokeInvitation(id));
}
