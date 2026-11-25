import { randomBytes } from 'node:crypto';
import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect, Schema } from 'effect';
import { RequestUid } from '#lib/contracts/v1/common.ts';
import type { ShareFeed } from '#lib/contracts/v1/feed.ts';
import { SentShareOp } from '#lib/contracts/v1/ops.ts';
import { apiError } from './api';
import { wakeRoomStreams } from './live-streams';
import { uuid } from './op-domain';
import { requireRoomAccess } from './room-access';
import { readFeedItems, readFeedLists } from './room-feed';
import { submitOpInTransaction, type prepareOp } from './room-ops';
import { readShareSeq, requireShareAccess } from './share-access';

const isListUid = Schema.is(RequestUid);
const isShareOp = Schema.is(SentShareOp);

export function roomShareLink(slug: string, token: string | null, listUid: string, reset = false) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const link = yield* sql.withTransaction(
			Effect.gen(function* () {
				const room = yield* requireRoomAccess(slug, token);
				if (!isListUid(listUid)) return yield* apiError(404, 'list_unavailable');
				const [list] = yield* sql<{ id: number; share_token: string }>`
					SELECT id, share_token FROM lists WHERE room_id = ${room.id} AND uid = ${uuid(listUid)}
				`;
				if (!list) return yield* apiError(404, 'list_unavailable');
				if (!reset) return { roomId: room.id, token: list.share_token };

				// Rotation is not a replayable op. Do not store the new token as an answer.
				const next = randomBytes(32).toString('base64url');
				yield* sql`UPDATE lists SET share_token = ${next} WHERE id = ${list.id}`;
				return { roomId: room.id, token: next };
			})
		);
		if (reset) wakeRoomStreams(link.roomId);
		return { token: link.token };
	});
}

export function readShareFeed(token: string, roomTokenFor: (slug: string) => string | null) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		return yield* sql.withTransaction(
			Effect.gen(function* () {
				const share = yield* requireShareAccess(token);
				const { id, roomId, roomSlug } = share;
				const room = yield* requireRoomAccess(roomSlug, roomTokenFor(roomSlug)).pipe(
					Effect.map(({ name, slug }) => ({ name, slug })),
					Effect.catchTag('ApiError', () => Effect.succeed(null))
				);
				const lists = yield* readFeedLists(roomId, -1, id);
				const items = yield* readFeedItems(roomId, -1, id);
				return {
					seq: yield* readShareSeq(share),
					full: true,
					room,
					lists: lists.map((list) => ({ ...list, slug: '' as const })),
					items,
					deletions: []
				} satisfies typeof ShareFeed.Type;
			})
		);
	});
}

export function submitShareOp(token: string, prepared: ReturnType<typeof prepareOp>) {
	return Effect.gen(function* () {
		if (!isShareOp(prepared.op))
			return yield* apiError(422, 'invalid_request', 'A share link cannot do this.');
		const sql = yield* SqliteClient.SqliteClient;
		const { roomId, result } = yield* sql.withTransaction(
			Effect.gen(function* () {
				const { id, uid, roomId } = yield* requireShareAccess(token);
				const result = yield* submitOpInTransaction({ roomId, sharedList: { id, uid } }, prepared);
				return { roomId, result };
			})
		);
		if (!result.replayed && result.answer.status === 'applied') wakeRoomStreams(roomId);
		return result;
	});
}
