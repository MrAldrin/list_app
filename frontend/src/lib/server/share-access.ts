import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { apiError } from './api';

type SharedList = { id: number; uid: string };
type ShareAccess = SharedList & { roomId: number; roomSlug: string };

// Call inside the transaction for the read, write or live cursor check.
export function requireShareAccess(token: string) {
	return Effect.gen(function* () {
		// Existing tokens, like new ones, are 32 random bytes in unpadded base64url.
		if (token.length !== 43) return yield* apiError(401, 'share_unavailable');
		const sql = yield* SqliteClient.SqliteClient;
		const [share] = yield* sql<ShareAccess>`
			SELECT l.id, l.uid, r.id AS roomId, r.slug AS roomSlug
			FROM lists AS l JOIN rooms AS r ON r.id = l.room_id
			WHERE l.share_token = ${token}
		`;
		if (!share) return yield* apiError(401, 'share_unavailable');
		return share;
	});
}

// Match the cursor in shared op answers, even after deletion rows are pruned.
export function readShareSeq({ id, uid }: SharedList) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const [{ seq }] = yield* sql<{ seq: number }>`
			SELECT COALESCE(MAX(seq), 0) AS seq FROM (
				SELECT changed_seq AS seq FROM lists WHERE id = ${id}
				UNION ALL SELECT changed_seq FROM items WHERE list_id = ${id}
				UNION ALL SELECT changed_seq FROM deletions WHERE list_uid = ${uid}
				UNION ALL SELECT changed_seq FROM share_seq_floors WHERE list_uid = ${uid}
			)
		`;
		return seq;
	});
}
