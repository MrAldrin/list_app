// Due items: unchecked items with a date, grouped for the due bell and counted
// on the room and list pages. Dates are calendar days (`YYYY-MM-DD`) in the
// device's own time zone. Pure rules, so Vitest can test them. See
// docs/due-date-reminders.md.

import { compareCodePoints } from '#lib/data/order.ts';
import type { Item } from '#lib/data/types.ts';

/** Disjoint groups, from the most urgent: overdue, today, tomorrow, days 2–7, then beyond day 7. */
export type DueGroup = 'overdue' | 'today' | 'tomorrow' | 'next7' | 'later';

/** The groups in the order they show. */
export const DUE_GROUPS: readonly DueGroup[] = ['overdue', 'today', 'tomorrow', 'next7', 'later'];

export const DUE_GROUP_TITLES: Record<DueGroup, string> = {
	overdue: 'Overdue',
	today: 'Today',
	tomorrow: 'Tomorrow',
	next7: 'Next 7 days',
	later: 'Later'
};

const DAY_MS = 86_400_000;

/** A day as `YYYY-MM-DD` in the device's own time zone. */
export function localDay(now: Date, zone?: string): string {
	if (zone) {
		try {
			const parts = new Intl.DateTimeFormat('en-CA', {
				timeZone: zone,
				year: 'numeric',
				month: '2-digit',
				day: '2-digit'
			}).formatToParts(now);
			const part = (name: string) => parts.find((p) => p.type === name)?.value;
			return `${part('year')}-${part('month')}-${part('day')}`;
		} catch {
			/* Browser fallback if the configured zone is unavailable. */
		}
	}
	const pad = (value: number) => String(value).padStart(2, '0');
	return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** The day's number since 1970-01-01, counted in UTC so daylight saving never shifts it. */
function dayNumber(day: string): number {
	const [year, month, date] = day.split('-').map(Number);
	// setUTCFullYear, not Date.UTC: Date.UTC maps years 0-99 to 1900-1999.
	const when = new Date(0);
	when.setUTCFullYear(year, month - 1, date);
	return Math.round(when.getTime() / DAY_MS);
}

/** Whole calendar days from `today` to `date`; negative when `date` has passed. */
export function daysBetween(today: string, date: string): number {
	return dayNumber(date) - dayNumber(today);
}

/** The group of a day, counted from `today` (both `YYYY-MM-DD`). */
export function dueGroupOfDay(date: string, today: string): DueGroup {
	const days = daysBetween(today, date);
	if (days < 0) return 'overdue';
	if (days === 0) return 'today';
	if (days === 1) return 'tomorrow';
	// Days 2–7 after today; the rest is later.
	return days <= 7 ? 'next7' : 'later';
}

/** The due group of an item, or null when it is done or has no date. */
export function itemDueGroup(
	item: Pick<Item, 'date' | 'done' | 'due_at'>,
	now: Date,
	zone?: string
): DueGroup | null {
	if (item.done || item.date === null) return null;
	if (item.due_at) {
		const instant = new Date(item.due_at);
		if (Number.isFinite(instant.valueOf())) {
			if (instant.valueOf() < now.valueOf()) return 'overdue';
			return dueGroupOfDay(localDay(instant, zone), localDay(now, zone));
		}
	}
	// Date-only items and unconfirmed wall intents have no invented instant.
	return dueGroupOfDay(item.date, localDay(now, zone));
}

/** Unchecked items overdue, due today or due tomorrow; `overdue` is the part past due. */
export interface DueTally {
	count: number;
	overdue: number;
}

/** The counts on the bell and on list cards. */
export function dueTally(items: readonly Item[], now: Date, zone?: string): DueTally {
	const tally: DueTally = { count: 0, overdue: 0 };
	for (const item of items) {
		const group = itemDueGroup(item, now, zone);
		if (group === 'overdue') tally.overdue += 1;
		if (group === 'overdue' || group === 'today' || group === 'tomorrow') tally.count += 1;
	}
	return tally;
}

/** A badge number: `99+` above 99, nothing at zero. */
export function badgeText(count: number): string {
	return count > 99 ? '99+' : String(count);
}

/** One dated, unchecked item in the due views. */
export interface DueRow {
	item: Item;
	/** `YYYY-MM-DD`, from the item. */
	date: string;
	/** The name of the item's list, for the whole-room view. */
	listName: string;
	group: DueGroup;
}

/**
 * The due rows of `items` (done and undated items are left out), in order:
 * by day, then list name, item name and UID, so ties keep one place.
 */
export function dueRows(
	items: readonly Item[],
	listName: (listUid: string) => string,
	now: Date,
	zone?: string
): DueRow[] {
	const rows: DueRow[] = [];
	for (const item of items) {
		if (item.done || item.date === null) continue;
		rows.push({
			item,
			date:
				item.due_at && Number.isFinite(Date.parse(item.due_at))
					? localDay(new Date(item.due_at), zone)
					: item.date,
			listName: listName(item.list_uid),
			group: itemDueGroup(item, now, zone)!
		});
	}
	// `YYYY-MM-DD` text sorts like the days it names.
	return rows.sort(
		(a, b) =>
			compareCodePoints(a.date, b.date) ||
			compareCodePoints(a.listName, b.listName) ||
			compareCodePoints(a.item.name, b.item.name) ||
			compareCodePoints(a.item.uid, b.item.uid)
	);
}

/** One group of the due views. */
export interface DueSection {
	group: DueGroup;
	rows: DueRow[];
}

/** The rows split into their groups, in display order; groups without rows are left out. */
export function dueSections(rows: readonly DueRow[]): DueSection[] {
	return DUE_GROUPS.map((group) => ({
		group,
		rows: rows.filter((row) => row.group === group)
	})).filter((section) => section.rows.length > 0);
}

/** The date label next to an item: text and color. Later and next-7 days have none. */
export function dueTag(group: DueGroup): { text: string; tone: 'danger' | 'warning' } | null {
	if (group === 'overdue') return { text: 'Overdue', tone: 'danger' };
	if (group === 'today') return { text: 'Today', tone: 'warning' };
	if (group === 'tomorrow') return { text: 'Tomorrow', tone: 'warning' };
	return null;
}
