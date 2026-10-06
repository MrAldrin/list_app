// A share link, seen by the data layer as a small room: one list, opened by
// its token instead of a room cookie (docs/api.md, "Share links").
//
// `ShareApi` answers the calls a `RoomHandle` makes with the share endpoints,
// so the store, the write queue and live updates work unchanged. The token
// takes the place of the room slug. A share link never gives room access:
// the room-only calls fail without asking the server (a room member's
// reset of the link is the one exception, see `resetShareLink`).

import type { Api } from './api';
import { ApiError } from './types';
import type { Feed, OpResponse, Room, SentOp, ShareLink } from './types';
import type { RoomApi } from './index';

/** What "who am I" answers for a working link: the link opens no room. */
const NO_ROOM: Room = { slug: '', name: '' };

function notForShareLinks(): Promise<never> {
	return Promise.reject(new ApiError(403, 'invalid_request', 'A share link cannot do this.'));
}

export class ShareApi implements RoomApi {
	readonly #api: Pick<Api, 'shareChanges' | 'sendShareOp' | 'shareEventsUrl' | 'resetShareLink'>;

	constructor(
		api: Pick<Api, 'shareChanges' | 'sendShareOp' | 'shareEventsUrl' | 'resetShareLink'>
	) {
		this.#api = api;
	}

	/** The room slug per link, while the feed says this browser is a member. */
	readonly #roomSlugs = new Map<string, string>();

	async changes(token: string, since: number): Promise<Feed> {
		const feed = await this.#api.shareChanges(token, since);
		if (feed.room) this.#roomSlugs.set(token, feed.room.slug);
		else this.#roomSlugs.delete(token);
		return feed;
	}

	sendOp(token: string, op: SentOp): Promise<OpResponse> {
		return this.#api.sendShareOp(token, op);
	}

	eventsUrl(token: string): string {
		return this.#api.shareEventsUrl(token);
	}

	/**
	 * Whether the link still works (after the stream closed or sent
	 * `revoked`). A reset link answers 401, which the handle treats like a
	 * sign-out: the page then says the link no longer works.
	 */
	whoAmI(token: string): Promise<Room> {
		return this.#api.shareChanges(token, 0).then(() => NO_ROOM);
	}

	/** The holder shares the link they have; no server call. */
	shareLink(token: string): Promise<ShareLink> {
		return Promise.resolve({ token });
	}

	login(): Promise<Room> {
		return notForShareLinks();
	}

	changePassword(): Promise<Room> {
		return notForShareLinks();
	}

	deleteRoom(): Promise<void> {
		return notForShareLinks();
	}

	/**
	 * Only room members can reset a link: the feed names the room only for
	 * them (decision 146), and the reset goes through the room's own endpoint,
	 * which checks the room cookie again.
	 */
	resetShareLink(token: string, listUid: string): Promise<ShareLink> {
		const slug = this.#roomSlugs.get(token);
		return slug ? this.#api.resetShareLink(slug, listUid) : notForShareLinks();
	}
}
