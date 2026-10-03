// Which checked items are hidden: a port of src/item_visibility.py.
// Rules: docs/checked-item-visibility.md. The API sends every item; the client hides.

import { compareCodePoints } from './order';
import type { HideDone, HideDoneMode, Item } from './types';

export const DEFAULT_HIDE_DONE: HideDone = { mode: 'off', age_days: 7, recent_count: 10 };
export const MAX_HIDE_DONE_COUNT = 100_000;
export const HIDE_DONE_MODES: readonly HideDoneMode[] = ['off', 'all', 'age', 'recent'];

const MICROS_PER_DAY = 24 * 60 * 60 * 1_000_000;

/** Throws for an unknown mode or a count that is not a whole number from 0 to 100,000. */
export function validateVisibilitySettings(mode: string, ageDays: number, recentCount: number) {
	if (!(HIDE_DONE_MODES as readonly string[]).includes(mode)) {
		throw new Error(`Unknown checked-item visibility mode: ${JSON.stringify(mode)}`);
	}
	for (const [name, value] of [
		['age_days', ageDays],
		['recent_count', recentCount]
	] as const) {
		if (!Number.isInteger(value) || value < 0 || value > MAX_HIDE_DONE_COUNT) {
			throw new Error(`${name} must be a whole number between 0 and ${MAX_HIDE_DONE_COUNT}`);
		}
	}
}

const ISO_TIME =
	/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?)?(Z|[+-]\d{2}(?::?\d{2})?)?$/i;

/**
 * An ISO 8601 time as microseconds since 1970 (UTC), or null if unreadable.
 * A time without a zone counts as UTC, like Python's `parse_completion_time`.
 * `Date.parse` is not used: it reads such times as local time, and browsers
 * differ on more than three fraction digits.
 */
export function parseCompletionTime(value: unknown): number | null {
	if (typeof value !== 'string' || !value) return null;
	const match = ISO_TIME.exec(value);
	if (!match) return null;
	const [, year, month, day, hour = '0', minute = '0', second = '0', fraction = '', zone] = match;
	const millis = Date.UTC(+year, +month - 1, +day, +hour, +minute, +second);
	const date = new Date(millis);
	// Reject overflowing parts such as month 13 or hour 25.
	if (
		date.getUTCMonth() !== +month - 1 ||
		date.getUTCDate() !== +day ||
		date.getUTCHours() !== +hour ||
		+minute > 59 ||
		+second > 59
	) {
		return null;
	}
	let micros = millis * 1000 + Number(fraction.slice(0, 6).padEnd(6, '0'));
	if (zone && zone.toUpperCase() !== 'Z') {
		const sign = zone.startsWith('-') ? -1 : 1;
		const digits = zone.slice(1).replace(':', '');
		const offsetMinutes = Number(digits.slice(0, 2)) * 60 + Number(digits.slice(2, 4) || '0');
		micros -= sign * offsetMinutes * 60 * 1_000_000;
	}
	return micros;
}

/**
 * The visible items, in their given order. Unchecked items always show.
 *
 * Call it on the whole list before a tag filter, so `recent` counts across the
 * whole list. In `age` mode, checked items without a time stay visible; in
 * `recent` mode they rank after known times (ties: no fixed order, here by uid).
 */
export function filterVisibleItems<T extends Pick<Item, 'done' | 'completed_at' | 'uid'>>(
	items: readonly T[],
	settings: HideDone = DEFAULT_HIDE_DONE,
	now: Date = new Date()
): T[] {
	const { mode, age_days: ageDays, recent_count: recentCount } = settings;
	validateVisibilitySettings(mode, ageDays, recentCount);
	if (mode === 'off') return [...items];

	if (mode === 'all' || (mode === 'age' && ageDays === 0)) {
		return items.filter((item) => !item.done);
	}

	if (mode === 'age') {
		const cutoff = now.getTime() * 1000 - ageDays * MICROS_PER_DAY;
		return items.filter((item) => {
			if (!item.done) return true;
			const completedAt = parseCompletionTime(item.completed_at);
			return completedAt === null || completedAt > cutoff;
		});
	}

	const ranked = items
		.filter((item) => item.done)
		.map((item) => ({ item, time: parseCompletionTime(item.completed_at) }))
		.sort((a, b) => {
			if ((a.time === null) !== (b.time === null)) return a.time === null ? 1 : -1;
			if (a.time !== null && b.time !== null && a.time !== b.time) return b.time - a.time;
			return compareCodePoints(b.item.uid, a.item.uid);
		});
	const retained = new Set(ranked.slice(0, recentCount).map(({ item }) => item));
	return items.filter((item) => !item.done || retained.has(item));
}
