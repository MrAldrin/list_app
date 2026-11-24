import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import { randomBytes } from 'node:crypto';
import type { Invitation } from '#lib/contracts/v1/common.ts';
import { insertRoom, roomName } from './admin-rooms';
import { ApiError, apiError } from './api';
import { hashToken } from './room-cookies';
import { hashRoomPassword, validateNewRoomPassword } from './room-password';

const SEVEN_DAYS = 7 * 24 * 60 * 60;
const ROOM_LIMIT = 5;

type InvitationRow = {
	readonly id: number;
	readonly created_at: number;
	readonly expires_at: number;
	readonly revoked_at: number | null;
	readonly rooms_created: number;
};

const nowSeconds = () => Math.floor(Date.now() / 1000);
const utc = (seconds: number) => new Date(seconds * 1000).toISOString().replace('.000Z', 'Z');
const unavailable = () => apiError(404, 'invitation_unavailable');

function invitationMetadata(row: InvitationRow, now: number): typeof Invitation.Type {
	const status =
		row.revoked_at !== null
			? 'revoked'
			: row.expires_at <= now
				? 'expired'
				: row.rooms_created >= ROOM_LIMIT
					? 'inactive'
					: 'active';
	return {
		id: row.id,
		status,
		created_at: utc(row.created_at),
		expires_at: utc(row.expires_at),
		revoked_at: row.revoked_at === null ? null : utc(row.revoked_at)
	};
}

function pruneHistory(now: number) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const cutoff = now - SEVEN_DAYS;
		yield* sql`DELETE FROM room_invitations WHERE expires_at <= ${cutoff} OR revoked_at <= ${cutoff}`;
	});
}

export const listInvitations = Effect.gen(function* () {
	const sql = yield* SqliteClient.SqliteClient;
	return yield* sql.withTransaction(
		Effect.gen(function* () {
			const now = nowSeconds();
			yield* pruneHistory(now);
			const rows = yield* sql<InvitationRow>`
				SELECT id, created_at, expires_at, revoked_at, rooms_created
				FROM room_invitations ORDER BY id DESC
			`;
			return rows.map((row) => invitationMetadata(row, now));
		})
	);
});

export const issueInvitation = Effect.gen(function* () {
	const sql = yield* SqliteClient.SqliteClient;
	return yield* sql.withTransaction(
		Effect.gen(function* () {
			const now = nowSeconds();
			yield* pruneHistory(now);
			const token = randomBytes(32).toString('base64url');
			const [row] = yield* sql<InvitationRow>`
				INSERT INTO room_invitations (token_hash, created_at, expires_at)
				VALUES (${hashToken(token)}, ${now}, ${now + SEVEN_DAYS})
				RETURNING id, created_at, expires_at, revoked_at, rooms_created
			`;
			return { invitation: invitationMetadata(row, now), token };
		})
	);
});

export function revokeInvitation(id: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		// The route validates the range before SQL casts the text to a 64-bit integer.
		yield* sql`
			UPDATE room_invitations SET revoked_at = ${nowSeconds()}
			WHERE id = CAST(${id} AS INTEGER) AND revoked_at IS NULL
		`;
	});
}

function usableInvitation(hash: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		return sql`
			token_hash = ${hash} AND revoked_at IS NULL
			AND expires_at > ${nowSeconds()} AND rooms_created < ${ROOM_LIMIT}
		`;
	});
}

export function checkInvitation(token: string) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const usable = yield* usableInvitation(hashToken(token));
		const [row] = yield* sql`SELECT 1 FROM room_invitations WHERE ${usable}`;
		if (!row) return yield* unavailable();
	});
}

export function createInvitedRoom(token: string, name: string, password: string) {
	return Effect.gen(function* () {
		yield* checkInvitation(token);
		const normalized = yield* Effect.try({
			try: () => {
				const normalized = roomName(name, 'invitation');
				validateNewRoomPassword(password);
				return normalized;
			},
			catch: (error) => {
				if (error instanceof ApiError) return error;
				throw error;
			}
		});
		const hash = yield* hashRoomPassword(password);
		const sql = yield* SqliteClient.SqliteClient;
		return yield* sql.withTransaction(
			Effect.gen(function* () {
				const usable = yield* usableInvitation(hashToken(token));
				const [counted] = yield* sql`
					UPDATE room_invitations SET rooms_created = rooms_created + 1
					WHERE ${usable} RETURNING id
				`;
				if (!counted) return yield* unavailable();
				return yield* insertRoom(normalized, randomBytes(18).toString('base64url'), hash);
			})
		);
	});
}
