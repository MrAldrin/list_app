import { randomBytes } from 'node:crypto';
import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect } from 'effect';
import {
	DeviceWriteResponse,
	EnrollmentWriteResponse,
	type Device,
	type DevicePatchBody,
	type EnrollBody,
	type Enrollment,
	type EnrollmentPatchBody
} from '#lib/contracts/v1/reminders.ts';
import { apiError } from './api';
import { syncRoomPolicy } from './reminder-policies';
import {
	DEVICE_LIFETIME_SECONDS,
	checkRevision,
	enrollmentRow,
	grantState,
	personalOnce,
	reminderDigest,
	requireEnrollment,
	stamp,
	withReminderAccess,
	type DeviceRow,
	type EnrollmentRow,
	type ReminderAccess,
	type ReminderContext
} from './reminder-store';
import { instantText, validateZone } from './zoned-time';
import { hashToken } from './room-cookies';

type ExistingEnrollment = typeof EnrollmentWriteResponse.Type.enrollment;
const notEnrolled = { state: 'not_enrolled', revision: null } as const;

function enrollmentView(
	ctx: ReminderContext,
	device: Pick<DeviceRow, 'expires_at'>,
	row: EnrollmentRow
): ExistingEnrollment {
	const { mode, summary_time, revision, activated_at } = row;
	return { state: grantState(device, row, ctx.now), mode, summary_time, revision, activated_at };
}

function deviceView(row: DeviceRow): typeof Device.Type {
	const {
		revision,
		timezone,
		all_day_time,
		quiet_start,
		quiet_end,
		daily_cap,
		spacing_minutes,
		paused,
		content_privacy,
		overdue_repeat_days
	} = row;
	return {
		revision,
		timezone,
		all_day_time,
		quiet_hours:
			quiet_start !== null && quiet_end !== null ? { start: quiet_start, end: quiet_end } : null,
		daily_cap,
		spacing_minutes,
		paused: paused === 1,
		content_privacy,
		overdue_repeat_days
	};
}

function checkZone(zone: string) {
	return Effect.try({
		try: () => validateZone(zone),
		catch: () => apiError(422, 'invalid_request', 'Unknown time zone.')
	});
}

export function getEnrollment(access: ReminderAccess) {
	return withReminderAccess(access, (ctx) =>
		Effect.succeed<{ enrollment: typeof Enrollment.Type }>({
			enrollment:
				ctx.device && ctx.enrollment ? enrollmentView(ctx, ctx.device, ctx.enrollment) : notEnrolled
		})
	);
}

export function getDevice(access: ReminderAccess) {
	return withReminderAccess(access, ({ device }) =>
		Effect.succeed({ device: device ? deviceView(device) : null })
	);
}

export function enroll(access: ReminderAccess, body: typeof EnrollBody.Type) {
	return withReminderAccess(access, (ctx) =>
		Effect.gen(function* () {
			const sql = yield* SqliteClient.SqliteClient;
			const now = stamp(ctx.now);
			const deviceExpiry = ctx.now.add({ seconds: DEVICE_LIFETIME_SECONDS });
			const expiresAt = stamp(deviceExpiry);
			let secret = access.deviceSecret ?? '';
			let deviceId: number;
			if (ctx.device) {
				deviceId = ctx.device.id;
			} else {
				if (body.timezone == null)
					return yield* apiError(422, 'invalid_request', 'A time zone is required.');
				yield* checkZone(body.timezone);
				secret = randomBytes(32).toString('base64url');
				const [device] = yield* sql<{ id: number }>`
				INSERT INTO reminder_installations (secret_hash, timezone, created_at, expires_at, anchor_activated_at, timezone_activated_at)
				VALUES (${hashToken(secret)}, ${body.timezone}, ${now}, ${expiresAt}, ${now}, ${now}) RETURNING id
			`;
				deviceId = device.id;
			}
			const { roomId, tokenHash } = ctx;
			const prior = ctx.enrollment;
			const result = yield* personalOnce(
				ctx,
				deviceId,
				'enrollment',
				body.op_id,
				reminderDigest('enroll', body),
				EnrollmentWriteResponse,
				Effect.gen(function* () {
					if (ctx.device && body.timezone != null && body.timezone !== ctx.device.timezone) {
						return yield* apiError(
							422,
							'invalid_request',
							'Change the device time zone in the device settings.'
						);
					}
					yield* checkRevision(prior?.revision ?? null, body.base_revision ?? null);
					if (!prior) {
						const [limits] = yield* sql<{ device_count: number; room_count: number }>`SELECT
						(SELECT COUNT(*) FROM reminder_enrollments WHERE installation_id = ${deviceId}) AS device_count,
						(SELECT COUNT(*) FROM reminder_enrollments WHERE room_id = ${roomId}) AS room_count`;
						if (limits.device_count >= 20)
							return yield* apiError(
								422,
								'invalid_request',
								'This device has enrolled in too many rooms.'
							);
						if (limits.room_count >= 50)
							return yield* apiError(
								422,
								'invalid_request',
								'This room has too many reminder devices.'
							);
					}
					const [token] = yield* sql<{ authorization_version: number; created_at: string }>`
					SELECT authorization_version, created_at FROM room_access_tokens
					WHERE room_id = ${roomId} AND token_hash = ${tokenHash}
				`;
					const tokenExpiry = Temporal.Instant.from(token.created_at.replace(' ', 'T') + 'Z').add({
						seconds: DEVICE_LIFETIME_SECONDS
					});
					const grantExpiry = stamp(
						Temporal.Instant.compare(deviceExpiry, tokenExpiry) < 0 ? deviceExpiry : tokenExpiry
					);
					const mode = body.mode ?? prior?.mode ?? 'daily_summary';
					const summary = body.summary_time ?? prior?.summary_time ?? '09:00';
					yield* sql`UPDATE reminder_installations SET expires_at = ${expiresAt} WHERE id = ${deviceId}`;
					if (!prior) {
						yield* sql`
						INSERT INTO reminder_enrollments (installation_id, room_id, token_hash, authorization_version,
							status, mode, summary_time, revision, activated_at, expires_at, created_at, policy_activated_at, summary_activated_at)
						VALUES (${deviceId}, ${roomId}, ${tokenHash}, ${token.authorization_version}, 'active', ${mode}, ${summary},
							1, ${now}, ${grantExpiry}, ${now}, ${now}, ${now})
					`;
					} else {
						const enrolled = yield* requireEnrollment(ctx);
						const activation =
							grantState(enrolled.device, prior, ctx.now) === 'active' ? prior.activated_at : now;
						yield* sql`UPDATE reminder_enrollments SET token_hash = ${tokenHash}, authorization_version = ${token.authorization_version},
						status = 'active', mode = ${mode}, summary_time = ${summary}, activated_at = ${activation}, expires_at = ${grantExpiry},
						revision = revision + 1 WHERE installation_id = ${deviceId} AND room_id = ${roomId}`;
						yield* syncRoomPolicy(enrolled, mode, summary !== prior.summary_time);
					}
					const row = yield* enrollmentRow(deviceId, roomId);
					if (!row) return yield* apiError(500, 'internal_error');
					return { enrollment: enrollmentView(ctx, { expires_at: expiresAt }, row) };
				})
			);
			if (result.replay) {
				const current = yield* requireEnrollment(ctx);
				return {
					response: refreshEnrollment(ctx, result.response, current.device, current.enrollment),
					secret: null
				};
			}
			return { response: result.response, secret };
		})
	);
}

function refreshEnrollment(
	ctx: ReminderContext,
	response: { enrollment: ExistingEnrollment },
	device: DeviceRow,
	row: EnrollmentRow
): typeof EnrollmentWriteResponse.Type {
	return { enrollment: { ...response.enrollment, state: grantState(device, row, ctx.now) } };
}

export function patchEnrollment(access: ReminderAccess, body: typeof EnrollmentPatchBody.Type) {
	return withReminderAccess(access, (ctx) =>
		Effect.gen(function* () {
			const enrolled = yield* requireEnrollment(ctx);
			const { device, enrollment: prior } = enrolled;
			const { response, replay } = yield* personalOnce(
				ctx,
				device.id,
				'enrollment',
				body.op_id,
				reminderDigest('patch_preferences', body),
				EnrollmentWriteResponse,
				Effect.gen(function* () {
					yield* checkRevision(prior.revision, body.base_revision);
					const mode = body.mode ?? prior.mode;
					const summary = body.summary_time ?? prior.summary_time;
					const status = body.opted_out ? 'opted_out' : prior.status;
					if (mode === prior.mode && summary === prior.summary_time && status === prior.status)
						return { enrollment: enrollmentView(ctx, device, prior) };
					const sql = yield* SqliteClient.SqliteClient;
					yield* sql`UPDATE reminder_enrollments SET mode = ${mode}, summary_time = ${summary}, status = ${status},
					revision = revision + 1 WHERE installation_id = ${device.id} AND room_id = ${ctx.roomId}`;
					yield* syncRoomPolicy(enrolled, mode, summary !== prior.summary_time);
					const row = {
						...prior,
						mode,
						summary_time: summary,
						status,
						revision: prior.revision + 1
					};
					return { enrollment: enrollmentView(ctx, device, row) };
				})
			);
			return replay ? refreshEnrollment(ctx, response, device, prior) : response;
		})
	);
}

export function patchDevice(access: ReminderAccess, body: typeof DevicePatchBody.Type) {
	return withReminderAccess(access, (ctx) =>
		Effect.gen(function* () {
			const current = ctx.device;
			if (!current) return yield* apiError(403, 'not_enrolled');
			const { response } = yield* personalOnce(
				ctx,
				current.id,
				'installation',
				body.op_id,
				reminderDigest('', body),
				DeviceWriteResponse,
				Effect.gen(function* () {
					yield* checkRevision(current.revision, body.base_revision);
					if (body.timezone !== undefined) yield* checkZone(body.timezone);
					const next: DeviceRow = {
						...current,
						timezone: body.timezone ?? current.timezone,
						all_day_time: body.all_day_time ?? current.all_day_time,
						quiet_start:
							body.quiet_hours === undefined
								? current.quiet_start
								: (body.quiet_hours?.start ?? null),
						quiet_end:
							body.quiet_hours === undefined ? current.quiet_end : (body.quiet_hours?.end ?? null),
						daily_cap: body.daily_cap ?? current.daily_cap,
						spacing_minutes: body.spacing_minutes ?? current.spacing_minutes,
						paused: body.paused === undefined ? current.paused : body.paused ? 1 : 0,
						content_privacy: body.content_privacy ?? current.content_privacy,
						overdue_repeat_days:
							body.overdue_repeat_days === undefined
								? current.overdue_repeat_days
								: body.overdue_repeat_days
					};
					if ((Object.keys(next) as (keyof DeviceRow)[]).every((key) => next[key] === current[key]))
						return { device: deviceView(current) };
					const at = instantText(ctx.now);
					const zoneChanged = next.timezone !== current.timezone;
					const anchorChanged = zoneChanged || next.all_day_time !== current.all_day_time;
					const sql = yield* SqliteClient.SqliteClient;
					yield* sql`UPDATE reminder_installations SET timezone = ${next.timezone}, all_day_time = ${next.all_day_time},
					quiet_start = ${next.quiet_start}, quiet_end = ${next.quiet_end}, daily_cap = ${next.daily_cap},
					spacing_minutes = ${next.spacing_minutes}, paused = ${next.paused}, content_privacy = ${next.content_privacy},
					overdue_repeat_days = ${next.overdue_repeat_days}, revision = revision + 1,
					anchor_activated_at = ${anchorChanged ? at : current.anchor_activated_at},
					timezone_activated_at = ${zoneChanged ? at : current.timezone_activated_at} WHERE id = ${current.id}`;
					return { device: deviceView({ ...next, revision: current.revision + 1 }) };
				})
			);
			return response;
		})
	);
}
