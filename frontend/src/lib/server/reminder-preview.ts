import { Effect } from 'effect';
import type { Preview, PreviewBody } from '#lib/contracts/v1/reminders.ts';
import { apiError } from './api';
import { policyTarget, readPolicy, resolvePolicy, type DueItem } from './reminder-policies';
import { draftPolicy, type PolicyView, type Rule } from './reminder-rules';
import {
	grantState,
	requireEnrollment,
	withReminderAccess,
	type EnrolledContext,
	type ReminderAccess
} from './reminder-store';
import {
	inSupportedCalendar,
	instantText,
	UnknownTimeZone,
	validateZone,
	wallInstant
} from './zoned-time';

type Entry = (typeof Preview.Type.entries)[number];
type PreviewInput = {
	selected: PolicyView;
	lowerResets: PolicyView[];
	item: DueItem;
	device: EnrolledContext['device'];
	enrollment: EnrolledContext['enrollment'];
};

const compare = (a: Temporal.Instant, b: Temporal.Instant) => Temporal.Instant.compare(a, b);
const parseInstant = (value: string) => Temporal.Instant.from(value);
const afterCutoffs = (instant: Temporal.Instant, cutoffs: readonly string[]) =>
	cutoffs.every((cutoff) => compare(instant, parseInstant(cutoff)) >= 0);

class MissingDueInstant extends Error {}

function resolveRule(
	item: DueItem,
	day: Temporal.PlainDate,
	rule: Rule,
	device: PreviewInput['device']
) {
	if (rule.kind === 'fixed') return parseInstant(rule.instant);
	let at: Temporal.Instant;
	if (item.due_time && rule.basis !== 'calendar') {
		if (!item.due_at) throw new MissingDueInstant();
		at = parseInstant(item.due_at);
	} else {
		const anchor = rule.basis === 'calendar' ? day.subtract({ days: rule.amount }) : day;
		at = wallInstant(
			anchor,
			item.due_time ?? device.all_day_time,
			item.due_time ? (item.due_timezone ?? '') : device.timezone
		);
	}
	return rule.basis === 'elapsed' ? at.subtract({ minutes: rule.amount }) : at;
}

function quietEnd(instant: Temporal.Instant, device: PreviewInput['device']): string | null {
	const { timezone, quiet_start: start, quiet_end: end } = device;
	if (start === null || end === null) return null;
	validateZone(timezone);
	const day = instant.toZonedDateTimeISO(timezone).toPlainDate();
	const crossesMidnight = start > end;
	const yesterday = day.subtract({ days: 1 });
	const startDays = crossesMidnight && inSupportedCalendar(yesterday) ? [yesterday, day] : [day];
	for (const startDay of startDays) {
		if (compare(instant, wallInstant(startDay, start, timezone)) < 0) continue;
		const endAt = wallInstant(
			crossesMidnight ? startDay.add({ days: 1 }) : startDay,
			end,
			timezone
		);
		if (compare(instant, endAt) < 0) return instantText(endAt);
	}
	return null;
}

// Pure preview: use the saved due fields with the selected policy, and no
// clock, persistence, delivery or enrollment renewal inside this function.
function upcoming(
	{ selected, lowerResets, item, device, enrollment }: PreviewInput,
	now: Temporal.Instant
) {
	if (item.date === null) return { entries: [], reasons: ['undated'] };
	const day = Temporal.PlainDate.from(item.date);
	const reasons = new Set<string>();
	const note = (error: unknown) =>
		reasons.add(
			error instanceof UnknownTimeZone
				? 'timezone_unavailable'
				: error instanceof MissingDueInstant
					? 'missing_due_instant'
					: 'calendar_out_of_range'
		);
	const deferred = (instant: Temporal.Instant) => {
		try {
			return quietEnd(instant, device);
		} catch (error) {
			note(error);
			return null;
		}
	};
	const lowerCutoffs = lowerResets.flatMap((p) =>
		p.activated_at === null ? [] : [p.activated_at]
	);
	const safety = [enrollment.activated_at, ...lowerCutoffs];
	const base = selected.activated_at === null ? safety : [...safety, selected.activated_at];
	const relative = [...base];
	if (item.due_cycle_started_at !== null) relative.push(item.due_cycle_started_at);
	if (item.due_time === null) relative.push(device.anchor_activated_at);
	const grouped = new Map<string, Entry>();
	for (const rule of selected.rules) {
		try {
			const instant = resolveRule(item, day, rule, device);
			if (!inSupportedCalendar(instant.toZonedDateTimeISO('UTC').toPlainDate()))
				throw new RangeError();
			const cutoffs = rule.kind === 'fixed' ? [...safety, rule.activation] : relative;
			if (compare(instant, now) <= 0 || !afterCutoffs(instant, cutoffs)) continue;
			const at = instantText(instant);
			const key = rule.kind === 'fixed' ? `fixed:${rule.id}` : rule.key;
			const existing = grouped.get(at);
			if (existing) existing.keys.push(key);
			else
				grouped.set(at, {
					kind: 'rules',
					instant: at,
					keys: [key],
					deferred_until: deferred(instant),
					local_day: null
				});
		} catch (error) {
			note(error);
		}
	}
	const entries = [...grouped.values()];
	for (const entry of entries) entry.keys.sort();
	if (selected.summary_enabled) {
		try {
			validateZone(device.timezone);
			const summaryCutoffs = [
				...base,
				enrollment.summary_activated_at,
				device.timezone_activated_at
			];
			const cutoff = summaryCutoffs
				.map(parseInstant)
				.reduce((latest, other) => (compare(other, latest) > 0 ? other : latest), now);
			const today = cutoff.toZonedDateTimeISO(device.timezone).toPlainDate();
			const dueDay =
				item.due_time && item.due_at
					? parseInstant(item.due_at).toZonedDateTimeISO(device.timezone).toPlainDate()
					: day;
			const first = dueDay.subtract({ days: 1 });
			let candidate = Temporal.PlainDate.compare(first, today) > 0 ? first : today;
			// On the first candidate day the summary time might have passed.
			// Six days suffice for the first five contributions; no due horizon.
			for (
				let count = 0;
				count < 6 && inSupportedCalendar(candidate);
				count++, candidate = candidate.add({ days: 1 })
			) {
				const instant = wallInstant(candidate, enrollment.summary_time, device.timezone);
				if (compare(instant, now) <= 0 || !afterCutoffs(instant, summaryCutoffs)) continue;
				entries.push({
					kind: 'summary',
					instant: instantText(instant),
					keys: [],
					local_day: candidate.toString(),
					deferred_until: quietEnd(instant, device)
				});
			}
		} catch (error) {
			note(error);
		}
	}
	entries.sort((a, b) =>
		a.instant < b.instant
			? -1
			: a.instant > b.instant
				? 1
				: a.kind === b.kind
					? 0
					: a.kind === 'rules'
						? -1
						: 1
	);
	return { entries: entries.slice(0, 5), reasons: [...reasons].sort() };
}

export function previewReminder(access: ReminderAccess, body: typeof PreviewBody.Type) {
	return withReminderAccess(access, (ctx) =>
		Effect.gen(function* () {
			const enrolled = yield* requireEnrollment(ctx);
			const target = yield* policyTarget(ctx.roomId, 'item', body.item_uid ?? body.item_id ?? null);
			if (target.scope !== 'item') return yield* apiError(404, 'not_found');
			const { item } = target;
			const { device, enrollment } = enrolled;
			const { view: saved } = yield* readPolicy(enrolled, target);
			const provisional: string[] = [];
			const draft = body.draft;
			const own = draft
				? yield* Effect.try({
						try: () => ({
							...draftPolicy(draft, saved, ctx.now, () => {
								const id = crypto.randomUUID();
								provisional.push(id);
								return id;
							}),
							activated_at: instantText(ctx.now)
						}),
						catch: (error) =>
							apiError(422, 'invalid_request', error instanceof Error ? error.message : undefined)
					})
				: saved;
			const { selected, chain } = yield* resolvePolicy(enrolled, target, own);
			const reasons: string[] = [];
			const grant = grantState(device, enrollment, ctx.now);
			if (grant !== 'active') reasons.push(grant);
			if (device.paused) reasons.push('device_paused');
			const off = selected.state === 'off' || selected.preset === 'quiet';
			if (off && !body.draft) reasons.push('policy_off');
			if (!item.date) reasons.push('undated');
			if (item.done) reasons.push('completed');
			if (off && body.draft) reasons.push('policy_off');
			const result = reasons.length
				? { entries: [], reasons }
				: upcoming(
						{ selected, lowerResets: chain.slice(0, -1), item, device, enrollment },
						ctx.now
					);
			return {
				source: selected.scope,
				state: selected.state,
				preset: selected.preset,
				timezone: device.timezone,
				disabled_reasons: result.reasons,
				provisional_fixed_ids: provisional.sort(),
				entries: result.entries
			};
		})
	);
}
