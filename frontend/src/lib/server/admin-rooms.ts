import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { randomBytes } from 'node:crypto';
import { apiError } from './api';
import { wakeRoomStreams } from './live-streams';
import {
	deleteRoomInTransaction,
	replaceRoomPasswordInTransaction,
	roomBySlug
} from './room-access';
import { hashRoomPassword, validateNewRoomPassword } from './room-password';

type Room = { readonly slug: string; readonly name: string };
const ROOM_NAME_LIMIT = 100;

function nameWhitespace(character: string): boolean {
	// The existing rule includes NEL and the four ASCII separators, not BOM.
	return /\p{White_Space}/u.test(character) || (character >= '\x1c' && character <= '\x1f');
}

export function roomName(raw: string, via: 'admin' | 'invitation'): string {
	let start = 0;
	let end = raw.length;
	while (start < end && nameWhitespace(raw[start])) start++;
	while (end > start && nameWhitespace(raw[end - 1])) end--;
	const name = raw.slice(start, end);
	const tooLong = [...name].length > ROOM_NAME_LIMIT;
	if (!name || tooLong) {
		const message =
			via === 'invitation'
				? `Room name must contain 1-${ROOM_NAME_LIMIT} characters.`
				: tooLong
					? `Room name can be at most ${ROOM_NAME_LIMIT} characters`
					: 'Room name cannot be empty';
		throw apiError(422, 'invalid_request', message);
	}
	return name;
}

export function insertRoom(name: string, slug: string, passwordHash: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		yield* sql`INSERT INTO rooms (name, slug, password_hash) VALUES (${name}, ${slug}, ${passwordHash})`;
		return { slug, name };
	});
}

export const listAdminRooms = Effect.gen(function* () {
	const sql = yield* SqliteClient.SqliteClient;
	const rooms = yield* sql<Room>`SELECT slug, name FROM rooms ORDER BY name COLLATE NOCASE ASC`;
	return [...rooms];
});

export function createAdminRoom(name: string, password: string) {
	validateNewRoomPassword(password);
	const normalized = roomName(name, 'admin');
	return Effect.gen(function* () {
		const prefix = normalized.toLowerCase().replace(/[^a-z0-9]/gu, '-');
		const slug = `${prefix}-${randomBytes(3).toString('hex')}`;
		const hash = yield* hashRoomPassword(password);
		return yield* insertRoom(normalized, slug, hash);
	});
}

export function resetAdminRoomPassword(slug: string, replacement: string) {
	validateNewRoomPassword(replacement);
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const hash = yield* hashRoomPassword(replacement);
		const roomId = yield* sql.withTransaction(
			Effect.gen(function* () {
				const room = yield* roomBySlug(slug);
				if (!room) return yield* apiError(404, 'room_unavailable');
				yield* replaceRoomPasswordInTransaction(room.id, hash);
				return room.id;
			})
		);
		wakeRoomStreams(roomId);
	});
}

export function deleteAdminRoom(slug: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const roomId = yield* sql.withTransaction(
			Effect.gen(function* () {
				const room = yield* roomBySlug(slug);
				if (!room) return yield* apiError(404, 'room_unavailable');
				yield* deleteRoomInTransaction(room.id);
				return room.id;
			})
		);
		wakeRoomStreams(roomId);
	});
}
