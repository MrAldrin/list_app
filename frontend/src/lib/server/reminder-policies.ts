import { SqliteClient } from '@effect/sql-sqlite-bun';
import { Effect, Schema } from 'effect';
import {
	PolicyResponse,
	type PolicyBody,
	type RoomPolicyBody
} from '#lib/contracts/v1/reminders.ts';
import { RequestUid } from '#lib/contracts/v1/common.ts';
import { apiError } from './api';
import {
	draftPolicy,
	presetRules,
	relativeRule,
	samePolicy,
	type PolicyView,
	type Rule
} from './reminder-rules';
import {
	canonicalReminderUid,
	checkRevision,
	personalOnce,
	reminderDigest,
	requireEnrollment,
	withReminderAccess,
	type EnrolledContext,
	type ReminderAccess
} from './reminder-store';
import { instantText } from './zoned-time';
import { hashToken } from './room-cookies';

type Scope = PolicyView['scope'];
export type DueItem = {
	id: number;
	list_id: number;
	date: string | null;
	due_time: string | null;
	due_timezone: string | null;
	due_at: string | null;
	due_cycle_started_at: string | null;
	done: 0 | 1;
};
type Target =
	{ scope: 'room' } | { scope: 'list'; id: number } | { scope: 'item'; id: number; item: DueItem };
type RuleRow =
	| {
			kind: 'relative';
			basis: 'at_due' | 'elapsed' | 'calendar';
			amount: number;
	  }
	| {
			kind: 'fixed';
			fixed_id: string;
			wall_date: string;
			wall_time: string;
			timezone: string;
			instant: string;
			activation: string;
	  };
type PolicyRow = {
	id: number;
	state: PolicyView['state'];
	preset: PolicyView['preset'];
	summary_enabled: 0 | 1;
	revision: number;
	activated_at: string;
};
type SavedPolicy = { id: number | null; view: PolicyView };
const isUid = Schema.is(RequestUid);
const roomTarget = { scope: 'room' } as const;

export function policyTarget(roomId: number, scope: Scope, input: string | number | null) {
	return Effect.gen(function* () {
		if (scope === 'room') return roomTarget;
		const sql = yield* SqliteClient.SqliteClient;
		const numeric =
			(typeof input === 'number' && Number.isSafeInteger(input)) ||
			(typeof input === 'string' && /^[0-9]{1,19}$/.test(input));
		const id = numeric ? input : null;
		const uid = typeof input === 'string' && isUid(input) ? canonicalReminderUid(input) : null;
		if (scope === 'list') {
			const [list] = yield* sql<{
				id: number;
			}>`SELECT id FROM lists WHERE room_id = ${roomId} AND (id = ${id} OR uid = ${uid})`;
			if (list) return { scope, id: list.id } satisfies Target;
		} else {
			const [item] = yield* sql<DueItem>`
				SELECT i.id, i.list_id, i.date, i.due_time, i.due_timezone, i.due_at, i.due_cycle_started_at, i.done
				FROM items i JOIN lists l ON i.list_id = l.id
				WHERE l.room_id = ${roomId} AND (i.id = ${id} OR i.uid = ${uid})
			`;
			if (item) return { scope, id: item.id, item } satisfies Target;
		}
		return yield* apiError(404, 'not_found');
	});
}

export function readPolicy(ctx: EnrolledContext, target: Target) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const { scope } = target;
		const [row] = yield* sql<PolicyRow>`
			SELECT id, state, preset, summary_enabled, revision, activated_at FROM reminder_policies
			WHERE installation_id = ${ctx.device.id} AND room_id = ${ctx.roomId} AND scope = ${scope}
				AND list_id IS ${scope === 'list' ? target.id : null}
				AND item_id IS ${scope === 'item' ? target.id : null}
		`;
		const preset = scope === 'room' ? ctx.enrollment.mode : (row?.preset ?? null);
		const rules = row
			? yield* sql<RuleRow>`
			SELECT kind, basis, amount, fixed_id, wall_date, wall_time, timezone, instant, activation
			FROM reminder_policy_rules WHERE policy_id = ${row.id} ORDER BY position
		`
			: [];
		const view: PolicyView = {
			scope,
			preset,
			state: row?.state ?? (scope === 'room' ? 'replace' : 'inherit'),
			summary_enabled: row ? row.summary_enabled === 1 : preset === 'daily_summary',
			rules: row
				? rules.map((r): Rule =>
						r.kind === 'relative'
							? relativeRule(r.basis, r.amount)
							: {
									kind: 'fixed',
									id: r.fixed_id,
									date: r.wall_date,
									time: r.wall_time,
									timezone: r.timezone,
									instant: r.instant,
									activation: r.activation
								}
					)
				: presetRules(preset),
			revision: row?.revision ?? 0,
			activated_at:
				row?.activated_at ??
				(scope === 'room'
					? instantText(Temporal.Instant.from(ctx.enrollment.policy_activated_at))
					: null)
		};
		return { id: row?.id ?? null, view } satisfies SavedPolicy;
	});
}

export function resolvePolicy(ctx: EnrolledContext, target: Target, own: PolicyView) {
	return Effect.gen(function* () {
		const chain = [own];
		if (own.state === 'inherit' && target.scope === 'item') {
			chain.push((yield* readPolicy(ctx, { scope: 'list', id: target.item.list_id })).view);
		}
		if (chain.at(-1)?.state === 'inherit' && target.scope !== 'room') {
			chain.push((yield* readPolicy(ctx, roomTarget)).view);
		}
		const selected = chain.at(-1) ?? own;
		return { selected, chain };
	});
}

function savePolicy(
	ctx: EnrolledContext,
	target: Target,
	priorId: number | null,
	policy: PolicyView
) {
	return Effect.gen(function* () {
		const sql = yield* SqliteClient.SqliteClient;
		const { scope } = target;
		const { state, rules } = policy;
		const at = instantText(ctx.now);
		const preset = scope === 'room' ? null : policy.preset;
		const summary = Number(policy.summary_enabled);
		let id = priorId;
		if (id === null) {
			const [row] = yield* sql<{ id: number }>`
				INSERT INTO reminder_policies (installation_id, room_id, scope, list_id, item_id, state,
					preset, summary_enabled, revision, activated_at)
				VALUES (${ctx.device.id}, ${ctx.roomId}, ${scope}, ${scope === 'list' ? target.id : null},
					${scope === 'item' ? target.id : null}, ${state}, ${preset}, ${summary}, 1, ${at}) RETURNING id
			`;
			id = row.id;
		} else {
			yield* sql`UPDATE reminder_policies SET state = ${state}, preset = ${preset}, summary_enabled = ${summary},
				revision = revision + 1, activated_at = ${at} WHERE id = ${id}`;
			yield* sql`DELETE FROM reminder_policy_rules WHERE policy_id = ${id}`;
		}
		for (const [position, rule] of rules.entries()) {
			const fixed = rule.kind === 'fixed' ? rule : null;
			const relative = rule.kind === 'relative' ? rule : null;
			yield* sql`
				INSERT INTO reminder_policy_rules (policy_id, position, kind, basis, amount, fixed_id, wall_date,
					wall_time, timezone, instant, activation)
				VALUES (${id}, ${position}, ${rule.kind}, ${relative?.basis ?? null}, ${relative?.amount ?? null},
					${fixed?.id ?? null}, ${fixed?.date ?? null}, ${fixed?.time ?? null}, ${fixed?.timezone ?? null},
					${fixed?.instant ?? null}, ${fixed?.activation ?? null})
			`;
		}
		return { ...policy, activated_at: at, revision: policy.revision + 1 };
	});
}

// Enrollment settings and the room default describe one mode, not two.
export function syncRoomPolicy(
	ctx: EnrolledContext,
	mode: PolicyView['preset'],
	summaryChanged: boolean
) {
	return Effect.gen(function* () {
		const changedMode = mode !== ctx.enrollment.mode;
		if (!changedMode && !summaryChanged) return;
		const sql = yield* SqliteClient.SqliteClient;
		const { id, view } = yield* readPolicy(ctx, roomTarget);
		yield* savePolicy(
			ctx,
			roomTarget,
			id,
			changedMode
				? {
						...view,
						preset: mode,
						rules: presetRules(mode),
						summary_enabled: mode === 'daily_summary'
					}
				: view
		);
		const at = instantText(ctx.now);
		yield* sql`UPDATE reminder_enrollments SET policy_activated_at = ${at},
			summary_activated_at = ${summaryChanged ? at : ctx.enrollment.summary_activated_at}
			WHERE installation_id = ${ctx.device.id} AND room_id = ${ctx.roomId}`;
	});
}

export function getPolicy(access: ReminderAccess, scope: Scope, input: string | null) {
	return withReminderAccess(access, (ctx) =>
		Effect.gen(function* () {
			const enrolled = yield* requireEnrollment(ctx);
			const target = yield* policyTarget(ctx.roomId, scope, input);
			const { view } = yield* readPolicy(enrolled, target);
			const { selected } = yield* resolvePolicy(enrolled, target, view);
			return { policy: view, effective: selected };
		})
	);
}

export function putPolicy(
	access: ReminderAccess,
	scope: Scope,
	input: string | null,
	body: typeof PolicyBody.Type | typeof RoomPolicyBody.Type
) {
	return withReminderAccess(access, (ctx) =>
		Effect.gen(function* () {
			const enrolled = yield* requireEnrollment(ctx);
			const target = yield* policyTarget(ctx.roomId, scope, input);
			const bodyDigest = reminderDigest('replace_policy', {
				...body,
				preset: body.preset ?? null,
				rules: body.rules ?? [],
				summary_enabled: body.summary_enabled ?? false,
				summary_time: body.summary_time ?? null
			});
			const digest = hashToken(
				`${scope}:${target.scope === 'room' ? 'None' : target.id}:${bodyDigest}`
			);
			const result = yield* personalOnce(
				ctx,
				enrolled.device.id,
				'enrollment',
				body.op_id,
				digest,
				PolicyResponse,
				Effect.gen(function* () {
					const current = yield* readPolicy(enrolled, target);
					yield* checkRevision(current.view.revision, body.base_revision);
					const next = yield* Effect.try({
						try: () => draftPolicy(body, current.view, ctx.now),
						catch: (error) =>
							apiError(422, 'invalid_request', error instanceof Error ? error.message : undefined)
					});
					const changedTime =
						body.summary_time != null && body.summary_time !== enrolled.enrollment.summary_time;
					let policy = current.view;
					if (changedTime || !samePolicy(current.view, next)) {
						policy = yield* savePolicy(enrolled, target, current.id, next);
						if (scope === 'room') {
							const sql = yield* SqliteClient.SqliteClient;
							const at = instantText(ctx.now);
							yield* sql`UPDATE reminder_enrollments SET mode = ${next.preset},
							summary_time = ${body.summary_time ?? enrolled.enrollment.summary_time},
							policy_activated_at = ${at}, summary_activated_at = ${changedTime ? at : enrolled.enrollment.summary_activated_at},
							revision = revision + 1 WHERE installation_id = ${enrolled.device.id} AND room_id = ${ctx.roomId}`;
						}
					}
					const { selected } = yield* resolvePolicy(enrolled, target, policy);
					return { policy, effective: selected };
				})
			);
			return result.response;
		})
	);
}
