import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';

const pruneDeletions = Effect.gen(function* () {
	const sql = yield* SqliteClient.SqliteClient;
	yield* sql.withTransaction(
		Effect.gen(function* () {
			const rooms = yield* sql<{ room_id: number; floor: number }>`
				SELECT room_id, MAX(changed_seq) AS floor FROM deletions
				WHERE created_at < strftime('%Y-%m-%dT%H:%M:%fZ', 'now', '-90 days')
				GROUP BY room_id
			`;
			for (const { room_id, floor } of rooms) {
				// Prune the whole prefix, even if some of its dates are newer after a clock change.
				// A live list keeps its own cursor when we remove its deletion rows.
				yield* sql`
					INSERT INTO share_seq_floors (list_uid, changed_seq)
					SELECT d.list_uid, MAX(d.changed_seq) FROM deletions AS d
					JOIN lists AS l ON l.uid = d.list_uid AND l.room_id = d.room_id
					WHERE d.room_id = ${room_id} AND d.changed_seq <= ${floor}
					GROUP BY d.list_uid
					ON CONFLICT(list_uid) DO UPDATE SET changed_seq = MAX(changed_seq, excluded.changed_seq)
				`;
				yield* sql`DELETE FROM deletions WHERE room_id = ${room_id} AND changed_seq <= ${floor}`;
				yield* sql`UPDATE rooms SET deletions_pruned_seq = MAX(deletions_pruned_seq, ${floor}) WHERE id = ${room_id}`;
			}
			yield* sql`DELETE FROM share_seq_floors WHERE list_uid NOT IN (SELECT uid FROM lists WHERE uid IS NOT NULL)`;
		})
	);
});

// Run at startup and once per day. Shutdown stops the scoped timer.
export const maintainFeedDeletions = Effect.gen(function* () {
	yield* pruneDeletions;
	yield* Effect.forkScoped(
		Effect.forever(
			Effect.sleep('1 day').pipe(
				Effect.zipRight(pruneDeletions),
				Effect.catchAll(() => Effect.logWarning('Could not prune feed deletions'))
			)
		)
	);
});
