import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { requireRoomAccess } from './room-access';
import { readShareSeq, requireShareAccess } from './share-access';

export function readRoomCursor(slug: string, token: string | null) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		return yield* sql.withTransaction(
			Effect.gen(function* () {
				const { id } = yield* requireRoomAccess(slug, token);
				const [{ seq }] = yield* sql<{ seq: number }>`
					SELECT change_seq AS seq FROM rooms WHERE id = ${id}
				`;
				return { roomId: id, seq };
			})
		);
	});
}

export function readShareCursor(token: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		return yield* sql.withTransaction(
			Effect.gen(function* () {
				const share = yield* requireShareAccess(token);
				return { roomId: share.roomId, seq: yield* readShareSeq(share) };
			})
		);
	});
}
