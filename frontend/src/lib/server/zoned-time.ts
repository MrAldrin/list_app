/// <reference lib="esnext.temporal" />

export class UnknownTimeZone extends Error {}
export class CalendarOutOfRange extends RangeError {}

export function validateZone(zone: string): void {
	try {
		if (!/^[a-zA-Z0-9._+/-]+$/.test(zone) || /^[+-]/.test(zone)) throw new RangeError();
		new Temporal.ZonedDateTime(0n, zone);
	} catch {
		throw new UnknownTimeZone('Unknown time zone.');
	}
}

export function inSupportedCalendar(day: Temporal.PlainDate): boolean {
	return day.year >= 1 && day.year <= 9999;
}

export function wallInstant(day: Temporal.PlainDate, time: string, zone: string): Temporal.Instant {
	validateZone(zone);
	if (!inSupportedCalendar(day)) throw new CalendarOutOfRange();
	const wall = day.toPlainDateTime(Temporal.PlainTime.from(time));
	const first = wall.toZonedDateTime(zone, { disambiguation: 'earlier' });
	// In a fold, the earlier instant is valid. In a gap it is not the requested
	// wall time: take the transition itself, not a shifted wall time.
	const at = first.toPlainDateTime().equals(wall) ? first : first.getTimeZoneTransition('next');
	if (!at || !inSupportedCalendar(at.withTimeZone('UTC').toPlainDate()))
		throw new CalendarOutOfRange();
	return at.toInstant();
}

export const instantText = (at: Temporal.Instant) => at.toString({ fractionalSecondDigits: 3 });
