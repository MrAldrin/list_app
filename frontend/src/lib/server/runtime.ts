import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Config, Context, Effect, Layer, Logger, ManagedRuntime, Redacted } from 'effect';
import { isAbsolute } from 'node:path';

class ServerConfig extends Context.Tag('listr/ServerConfig')<
	ServerConfig,
	{ readonly filename: string }
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
	Config.map(databaseConfig, ({ filename }) => ({ filename }))
);
const DatabaseLive = Layer.unwrapEffect(
	Effect.map(ServerConfig, ({ filename }) =>
		SqliteClient.layer({
			filename,
			readonly: true,
			readwrite: false,
			create: false,
			disableWAL: true
		})
	)
).pipe(Layer.provide(ConfigLive));

// Startup and routes share this scope and connection.
export const runtime = ManagedRuntime.make(Layer.merge(DatabaseLive, Logger.json));

export const checkDatabase = Effect.gen(function* () {
	const sql = yield* SqliteClient.SqliteClient;
	yield* sql`SELECT slug FROM rooms LIMIT 0`;
	yield* Effect.logInfo('TypeScript server opened the test database read-only');
});
