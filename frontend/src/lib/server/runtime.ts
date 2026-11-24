import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Config, Context, Effect, Layer, Logger, ManagedRuntime, Redacted } from 'effect';
import { isAbsolute } from 'node:path';

export class ServerConfig extends Context.Tag('listr/ServerConfig')<
	ServerConfig,
	{ readonly filename: string; readonly appPassword: Redacted.Redacted }
>() {}

const databaseConfig = Config.all({
	filename: Config.string('DB_PATH').pipe(
		Config.validate({ message: 'Use an absolute path to a test database', validation: isAbsolute })
	),
	password: Config.redacted('APP_PASSWORD').pipe(
		Config.validate({
			message: 'APP_PASSWORD must not be blank',
			validation: (password) => Redacted.value(password).trim().length > 0
		})
	)
});

const ConfigLive = Layer.effect(
	ServerConfig,
	Config.map(databaseConfig, ({ filename, password }) => ({ filename, appPassword: password }))
);
const DatabaseLive = Layer.unwrapEffect(
	Effect.map(ServerConfig, ({ filename }) =>
		Layer.tap(SqliteClient.layer({ filename, create: false }), (context) => {
			const sql = Context.get(context, SqliteClient.SqliteClient);
			return Effect.gen(function* () {
				yield* sql`PRAGMA foreign_keys = ON`;
				const [setting] = yield* sql<{ foreign_keys: number }>`PRAGMA foreign_keys`;
				if (setting?.foreign_keys !== 1) yield* Effect.dieMessage('SQLite foreign keys are off');
			});
		})
	)
).pipe(Layer.provideMerge(ConfigLive));

// Startup and routes share this scope and connection.
export const runtime = ManagedRuntime.make(Layer.merge(DatabaseLive, Logger.json));

export const checkDatabase = Effect.gen(function* () {
	const sql = yield* SqliteClient.SqliteClient;
	yield* sql`SELECT slug, authorization_version FROM rooms LIMIT 0`;
	yield* sql`SELECT token_hash, authorization_version FROM room_access_tokens LIMIT 0`;
	yield* sql`SELECT token_hash, status, revision FROM reminder_enrollments LIMIT 0`;
	yield* Effect.logInfo('TypeScript server opened the test database');
});
