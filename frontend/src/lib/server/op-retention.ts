import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';

// Run at startup and once per day. The runtime scope stops the timer on shutdown.
export const maintainOpAnswers = Effect.gen(function* () {
	const sql = yield* SqliteClient.SqliteClient;
	const prune = sql`DELETE FROM processed_ops WHERE created_at < strftime('%Y-%m-%dT%H:%M:%fZ','now','-30 days')`;
	yield* prune;
	yield* Effect.forkScoped(
		Effect.forever(
			Effect.sleep('1 day').pipe(
				Effect.zipRight(prune),
				Effect.catchAll(() => Effect.logWarning('Could not prune operation answers'))
			)
		)
	);
});
