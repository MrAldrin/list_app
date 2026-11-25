import { SqliteClient } from '@effect/sql-sqlite-bun';
import type { SqlError } from '@effect/sql/SqlError';
import { Effect, Schema } from 'effect';
import type { Device, Mode } from '#lib/contracts/v1/reminders.ts';
import { apiError, type ApiError } from './api';
import { requireRoomAccess } from './room-access';
import { hashToken } from './room-cookies';

export const DEVICE_LIFETIME_SECONDS = 365 * 24 * 60 * 60;

// Expiry and enrollment timestamps use the existing whole-second UTC format.
export const stamp = (at: Temporal.Instant) => at.toString({ fractionalSecondDigits: 0 });

export type DeviceRow = Omit<typeof Device.Type, 'quiet_hours' | 'paused'> & {
	id: number;
	expires_at: string;
	quiet_start: string | null;
	quiet_end: string | null;
	paused: 0 | 1;
	anchor_activated_at: string;
	timezone_activated_at: string;
};
export type EnrollmentRow = {
	status: 'active' | 'revoked' | 'opted_out';
	mode: typeof Mode.Type;
	summary_time: string;
	revision: number;
	activated_at: string;
	expires_at: string;
	policy_activated_at: string;
	summary_activated_at: string;
	token_live: 0 | 1;
};
export type ReminderContext = {
	roomId: number;
	tokenHash: string;
	now: Temporal.Instant;
	device: DeviceRow | undefined;
	enrollment: EnrollmentRow | undefined;
};
export type EnrolledContext = ReminderContext & { device: DeviceRow; enrollment: EnrollmentRow };
export type ReminderEffect<A> = Effect.Effect<A, SqlError | ApiError, SqliteClient.SqliteClient>;
export type ReminderAccess = {
	slug: string;
	roomToken: string | null;
	deviceSecret: string | null;
};

export function enrollmentRow(deviceId: number, roomId: number) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const [row] = yield* sql<EnrollmentRow>`
			SELECT e.status, e.mode, e.summary_time, e.revision, e.activated_at, e.expires_at,
				e.policy_activated_at, e.summary_activated_at, EXISTS (
					SELECT 1 FROM rooms r JOIN room_access_tokens t ON t.room_id = r.id
					WHERE r.id = e.room_id AND t.token_hash = e.token_hash AND t.revoked_at IS NULL
						AND r.authorization_version = e.authorization_version
						AND t.authorization_version = r.authorization_version
				) AS token_live
			FROM reminder_enrollments e WHERE e.installation_id = ${deviceId} AND e.room_id = ${roomId}
		`;
		return row as EnrollmentRow | undefined;
	});
}

export function grantState(
	device: Pick<DeviceRow, 'expires_at'>,
	enrollment: EnrollmentRow,
	now: Temporal.Instant
) {
	if (enrollment.status === 'opted_out') return 'opted_out';
	const time = stamp(now);
	return enrollment.status === 'active' &&
		device.expires_at > time &&
		enrollment.expires_at > time &&
		enrollment.token_live === 1
		? 'active'
		: 'needs_resume';
}

export function withReminderAccess<A>(
	access: ReminderAccess,
	run: (ctx: ReminderContext) => ReminderEffect<A>
) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		return yield* sql.withTransaction(
			Effect.gen(function* () {
				const room = yield* requireRoomAccess(access.slug, access.roomToken);
				const now = Temporal.Now.instant();
				const secret = access.deviceSecret;
				const [device] = secret
					? yield* sql<DeviceRow>`
				SELECT id, expires_at, revision, timezone, all_day_time, quiet_start, quiet_end,
					daily_cap, spacing_minutes, paused, content_privacy, overdue_repeat_days,
					anchor_activated_at, timezone_activated_at
				FROM reminder_installations WHERE secret_hash = ${hashToken(secret)} AND expires_at > ${stamp(now)}
			`
					: [];
				const enrollment = device ? yield* enrollmentRow(device.id, room.id) : undefined;
				return yield* run({
					roomId: room.id,
					tokenHash: hashToken(access.roomToken ?? ''),
					now,
					device,
					enrollment
				});
			})
		);
	});
}

export function requireEnrollment(ctx: ReminderContext) {
	return ctx.device && ctx.enrollment
		? Effect.succeed({ ...ctx, device: ctx.device, enrollment: ctx.enrollment })
		: Effect.fail(apiError(403, 'not_enrolled'));
}

export function checkRevision(current: number | null, base: number | null) {
	return current === base ? Effect.void : Effect.fail(apiError(409, 'revision_conflict'));
}

export function canonicalReminderUid(uid: string): string {
	const compact = uid.toLowerCase().replace(/^urn:uuid:|[{}-]/g, '');
	return `${compact.slice(0, 8)}-${compact.slice(8, 12)}-${compact.slice(12, 16)}-${compact.slice(16, 20)}-${compact.slice(20)}`;
}

// Preserve the existing private op fingerprints: compact, sorted-key,
// ASCII JSON with canonical op_id. Optional fields stay absent unless sent;
// policy writes pass the legacy defaults explicitly before hashing.
function sortedAsciiJson(value: unknown): string {
	if (Array.isArray(value)) return `[${value.map(sortedAsciiJson).join(',')}]`;
	if (value !== null && typeof value === 'object') {
		return `{${Object.entries(value)
			.filter(([, v]) => v !== undefined)
			.sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
			.map(([k, v]) => `${sortedAsciiJson(k)}:${sortedAsciiJson(v)}`)
			.join(',')}}`;
	}
	return JSON.stringify(value).replace(
		/[\u007f-\uffff]/g,
		(char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`
	);
}

export function reminderDigest<T extends { op_id: string }>(action: string, body: T) {
	return hashToken(sortedAsciiJson({ action, ...body, op_id: canonicalReminderUid(body.op_id) }));
}

// Called only after current access, device and applicable enrollment/target
// checks. Stored responses and first writes are private to this namespace.
export function personalOnce<A, I>(
	ctx: ReminderContext,
	deviceId: number,
	scope: 'installation' | 'enrollment',
	requestId: string,
	digest: string,
	schema: Schema.Schema<A, I>,
	run: ReminderEffect<A>
) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const roomId = scope === 'enrollment' ? ctx.roomId : null;
		const opId = canonicalReminderUid(requestId);
		const [prior] = yield* sql<{ request_hash: string; response_json: string }>`
			SELECT request_hash, response_json FROM reminder_processed_ops
			WHERE scope = ${scope} AND installation_id = ${deviceId} AND room_id IS ${roomId} AND op_id = ${opId}
		`;
		if (prior) {
			if (prior.request_hash !== digest) return yield* apiError(409, 'op_id_reused');
			return {
				response: Schema.decodeUnknownSync(schema)(JSON.parse(prior.response_json)),
				replay: true
			};
		}
		const response = yield* run;
		const encoded = Schema.encodeSync(schema)(response);
		yield* sql`
			INSERT INTO reminder_processed_ops (scope, installation_id, room_id, op_id, request_hash, response_json, created_at)
			VALUES (${scope}, ${deviceId}, ${roomId}, ${opId}, ${digest}, ${JSON.stringify(encoded)}, ${stamp(ctx.now)})
		`;
		return { response, replay: false };
	});
}
