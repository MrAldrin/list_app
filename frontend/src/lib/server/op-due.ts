/// <reference lib="esnext.temporal" />
import { Effect } from 'effect';
import { Refusal } from './op-domain';

type Schedule = { date: string | null; due_time: string | null; due_timezone: string | null };
export const undated: Schedule = { date: null, due_time: null, due_timezone: null };
const invalid = () =>
	new Refusal({
		code: 'invalid_due',
		message:
			'A due time needs a date and a time zone; a time zone needs a due time. Clearing the date clears both.'
	});
export function mergeDue(stored: Schedule, op: Partial<Schedule>) {
	const date = op.date === undefined ? stored.date : op.date;
	if (!date)
		return op.due_time != null || op.due_timezone != null
			? Effect.fail(invalid())
			: Effect.succeed(undated);
	const due_time = op.due_time === undefined ? stored.due_time : op.due_time;
	if (!due_time)
		return op.due_timezone != null
			? Effect.fail(invalid())
			: Effect.succeed({ date, due_time: null, due_timezone: null });
	const due_timezone = op.due_timezone === undefined ? stored.due_timezone : op.due_timezone;
	return due_timezone === null
		? Effect.fail(invalid())
		: Effect.succeed({ date, due_time, due_timezone });
}
export function resolveDue({ date, due_time, due_timezone }: Schedule) {
	if (!date || !due_time || due_timezone === null) return Effect.succeed(null);
	return Effect.try({
		try: () => {
			if (!/^[a-zA-Z0-9._+/-]+$/.test(due_timezone) || /^[+-]/.test(due_timezone))
				throw new RangeError();
			const wall = Temporal.PlainDateTime.from(`${date}T${due_time}`);
			const first = wall.toZonedDateTime(due_timezone, { disambiguation: 'earlier' });
			// A fold uses its first instant. In a gap, use the transition itself, not the wall time plus the gap.
			const at = first.toPlainDateTime().equals(wall) ? first : first.getTimeZoneTransition('next');
			if (!at) throw invalid();
			const iso = at.toInstant().toString({ fractionalSecondDigits: 3 });
			if (!/^\d{4}-/.test(iso) || iso.startsWith('0000')) throw invalid();
			return iso;
		},
		catch: (cause) =>
			cause instanceof Refusal
				? cause
				: new Refusal({
						code: 'time_zone_unavailable',
						message: 'This time zone is not available on this server.'
					})
	});
}
export function cycle(date: string | null) {
	return date
		? { id: crypto.randomUUID(), start: new Date().toISOString() }
		: { id: null, start: null };
}
