import { randomBytes } from 'node:crypto';
import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { apiError } from './api';
import { wakeRoomStreams } from './live-streams';
import { hashToken } from './room-cookies';
import { hashRoomPassword, verifyRoomPassword } from './room-password';

type RoomState = {
	readonly id: number;
	readonly name: string;
	readonly slug: string;
	readonly password_hash: string;
	readonly authorization_version: number;
};
type RoomAccess = Pick<RoomState, 'id' | 'name' | 'slug'>;

// A non-secret bcrypt hash at the same cost as room passwords. Check it for
// unknown rooms so a wrong password and an unknown room both do password work.
const DUMMY_HASH = '$2b$12$vZXjh90ZwUCVld339APb7e3P35uCr5vKr4Fdt0TzguWaKfMiB0C3O';

export function roomBySlug(slug: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const rooms = yield* sql<RoomState>`
			SELECT id, name, slug, password_hash, authorization_version FROM rooms WHERE slug = ${slug}
		`;
		return rooms.at(0);
	});
}

function authorizedRoom(slug: string, token: string | null) {
	return Effect.gen(function* () {
		if (token === null) return yield* apiError(401, 'not_authenticated');
		const sql = yield* SqliteClient.SqliteClient;
		const [room] = yield* sql<RoomState>`
			SELECT r.id, r.name, r.slug, r.password_hash, r.authorization_version
			FROM rooms AS r
			WHERE r.slug = ${slug}
				AND EXISTS (
					SELECT 1 FROM room_access_tokens AS t
					WHERE t.room_id = r.id AND t.token_hash = ${hashToken(token)}
						AND t.authorization_version = r.authorization_version AND t.revoked_at IS NULL
				)
		`;
		if (!room) return yield* apiError(401, 'not_authenticated');
		return room;
	});
}

// Put this and any downstream reads or writes in the same transaction.
export function requireRoomAccess(slug: string, token: string | null) {
	return authorizedRoom(slug, token).pipe(
		Effect.map(({ id, name, slug }): RoomAccess => ({ id, name, slug }))
	);
}

function samePasswordState(checked: RoomState, current: RoomState | undefined): boolean {
	return (
		checked.id === current?.id &&
		checked.authorization_version === current.authorization_version &&
		checked.password_hash === current.password_hash
	);
}

function issueToken(roomId: number, version: number) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const token = randomBytes(32).toString('base64url');
		yield* sql`
			INSERT INTO room_access_tokens (room_id, token_hash, authorization_version)
			VALUES (${roomId}, ${hashToken(token)}, ${version})
		`;
		yield* sql`
			DELETE FROM room_access_tokens WHERE room_id = ${roomId} AND id NOT IN (
				SELECT id FROM room_access_tokens WHERE room_id = ${roomId} ORDER BY id DESC LIMIT 200
			)
		`;
		return token;
	});
}

export function signInToRoom(slug: string, password: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const checked = yield* roomBySlug(slug);
		const valid = yield* verifyRoomPassword(password, checked?.password_hash ?? DUMMY_HASH);
		if (!checked || !valid) return yield* apiError(401, 'invalid_password');

		// Password checks do not hold the SQLite lock. Check the version and
		// hash again before issuing a token for the room.
		return yield* sql.withTransaction(
			Effect.gen(function* () {
				const current = yield* roomBySlug(slug);
				if (!current || !samePasswordState(checked, current))
					return yield* apiError(401, 'invalid_password');
				const token = yield* issueToken(current.id, current.authorization_version);
				return { room: { slug: current.slug, name: current.name }, token };
			})
		);
	});
}

export function signOutOfRoom(slug: string, token: string | null) {
	return Effect.gen(function* () {
		if (token === null) return;
		const sql = yield* SqliteClient.SqliteClient;
		const hash = hashToken(token);
		const roomId = yield* sql.withTransaction(
			Effect.gen(function* () {
				const [revoked] = yield* sql<{ room_id: number }>`
				UPDATE room_access_tokens SET revoked_at = CURRENT_TIMESTAMP
				WHERE room_id = (SELECT id FROM rooms WHERE slug = ${slug}) AND token_hash = ${hash}
				RETURNING room_id
			`;
				yield* sql`
				UPDATE reminder_enrollments SET status = 'revoked', revision = revision + 1
				WHERE room_id = (SELECT id FROM rooms WHERE slug = ${slug})
					AND token_hash = ${hash} AND status = 'active'
			`;
				return revoked?.room_id;
			})
		);
		if (roomId !== undefined) wakeRoomStreams(roomId);
	});
}

// Reuse this for admin reset. Call in a write transaction after validating
// access and finding the room. The caller decides whether to issue a token.
export function replaceRoomPasswordInTransaction(roomId: number, newHash: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const rows = yield* sql<{ authorization_version: number }>`
			UPDATE rooms SET password_hash = ${newHash}, authorization_version = authorization_version + 1
			WHERE id = ${roomId} RETURNING authorization_version
		`;
		const updated = rows.at(0);
		if (!updated) return yield* apiError(404, 'room_unavailable');
		yield* sql`DELETE FROM room_access_tokens WHERE room_id = ${roomId}`;
		yield* sql`
			UPDATE reminder_enrollments SET status = 'revoked', revision = revision + 1
			WHERE room_id = ${roomId} AND status = 'active'
		`;
		return updated.authorization_version;
	});
}

export function changeRoomPassword(
	slug: string,
	token: string | null,
	current: string,
	replacement: string
) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const checked = yield* authorizedRoom(slug, token);
		const wrong = apiError(403, 'wrong_password', 'Incorrect current password');
		if (!(yield* verifyRoomPassword(current, checked.password_hash))) return yield* wrong;
		const newHash = yield* hashRoomPassword(replacement);

		const { roomId, ...session } = yield* sql.withTransaction(
			Effect.gen(function* () {
				const room = yield* authorizedRoom(slug, token);
				if (!samePasswordState(checked, room)) return yield* wrong;
				const version = yield* replaceRoomPasswordInTransaction(room.id, newHash);
				const newToken = yield* issueToken(room.id, version);
				return { roomId: room.id, room: { slug: room.slug, name: room.name }, token: newToken };
			})
		);
		wakeRoomStreams(roomId);
		return session;
	});
}

// Reuse this for admin deletion. The existing schema does not cascade all
// lists/items, so remove them before the room in the same write transaction.
export function deleteRoomInTransaction(roomId: number) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		yield* sql`DELETE FROM items WHERE list_id IN (SELECT id FROM lists WHERE room_id = ${roomId})`;
		yield* sql`DELETE FROM lists WHERE room_id = ${roomId}`;
		yield* sql`DELETE FROM rooms WHERE id = ${roomId}`;
	});
}

export function deleteRoomWithPassword(slug: string, token: string | null, password: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const checked = yield* authorizedRoom(slug, token);
		const wrong = apiError(403, 'wrong_password');
		if (!(yield* verifyRoomPassword(password, checked.password_hash))) return yield* wrong;
		const roomId = yield* sql.withTransaction(
			Effect.gen(function* () {
				const room = yield* authorizedRoom(slug, token);
				if (!samePasswordState(checked, room)) return yield* wrong;
				yield* deleteRoomInTransaction(room.id);
				return room.id;
			})
		);
		wakeRoomStreams(roomId);
	});
}
