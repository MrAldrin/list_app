// Due-date reminders inside the app (no server, no permissions). An item is
// "due soon" when it is not checked and its date is tomorrow or earlier
// (overdue counts too). See docs/due-date-reminders.md.
//
// Two moments show a reminder toast:
// - opening a list: every due item of that list, every time it opens;
// - a check across all lists (on load and every few minutes): only items not
//   yet reminded about on this page, so the same item does not nag.

import type { Item, List } from '#lib/data/types.ts';

/** How often the app checks all lists again, in milliseconds. */
export const DUE_CHECK_INTERVAL_MS = 5 * 60_000;

/** A day as `YYYY-MM-DD` in the device's own time zone. */
export function localDay(now: Date): string {
	const pad = (value: number) => String(value).padStart(2, '0');
	return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function nextDay(now: Date): Date {
	return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
}

/** The unchecked items dated tomorrow or earlier. */
export function dueItems(items: readonly Item[], now: Date): Item[] {
	const tomorrow = localDay(nextDay(now));
	// `YYYY-MM-DD` text sorts like the days it names.
	return items.filter((item) => !item.done && item.date !== null && item.date <= tomorrow);
}

function plural(count: number): string {
	return `${count} ${count === 1 ? 'item' : 'items'}`;
}

/** "2 items due: 1 overdue, 1 tomorrow". Assumes `due` came from `dueItems`. */
export function dueSummary(due: readonly Item[], now: Date): string {
	const today = localDay(now);
	let overdue = 0;
	let dueToday = 0;
	for (const item of due) {
		if (item.date! < today) overdue += 1;
		else if (item.date === today) dueToday += 1;
	}
	const tomorrow = due.length - overdue - dueToday;
	const parts = [
		overdue ? `${overdue} overdue` : '',
		dueToday ? `${dueToday} today` : '',
		tomorrow ? `${tomorrow} tomorrow` : ''
	].filter(Boolean);
	return `${plural(due.length)} due: ${parts.join(', ')}`;
}

/** A toast to show. `danger` when something is overdue, else `warning`. */
export interface DueReminder {
	message: string;
	kind: 'warning' | 'danger';
}

function reminder(message: string, due: readonly Item[], now: Date): DueReminder {
	const today = localDay(now);
	return { message, kind: due.some((item) => item.date! < today) ? 'danger' : 'warning' };
}

/** Remembers what this page has already reminded about. One per opened room or share link. */
export class DueReminders {
	// `uid@date`: a new date on the same item reminds again.
	readonly #reminded = new Set<string>();

	#mark(due: readonly Item[]): void {
		for (const item of due) this.#reminded.add(`${item.uid}@${item.date}`);
	}

	/** A list was opened: remind about all its due items. */
	listOpened(items: readonly Item[], now: Date): DueReminder | null {
		const due = dueItems(items, now);
		this.#mark(due);
		return due.length ? reminder(dueSummary(due, now), due, now) : null;
	}

	/** The periodic check across all lists: remind only about items not reminded yet. */
	checkAll(
		lists: readonly List[],
		itemsOf: (listUid: string) => readonly Item[],
		now: Date
	): DueReminder | null {
		const fresh: { list: List; due: Item[] }[] = [];
		for (const list of lists) {
			const due = dueItems(itemsOf(list.uid), now).filter(
				(item) => !this.#reminded.has(`${item.uid}@${item.date}`)
			);
			if (due.length) fresh.push({ list, due });
		}
		if (!fresh.length) return null;
		const all = fresh.flatMap(({ due }) => due);
		this.#mark(all);
		const message =
			fresh.length === 1
				? `${fresh[0].list.name}: ${dueSummary(fresh[0].due, now)}`
				: `Due soon: ${fresh.map(({ list, due }) => `${list.name} (${due.length})`).join(', ')}`;
		return reminder(message, all, now);
	}
}

/** The current time, read once per check (not a reactive value). */
export function clockNow(): Date {
	return new Date();
}
