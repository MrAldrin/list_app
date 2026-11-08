import { describe, expect, it } from 'vitest';
import { makeItem, makeList } from '#lib/data/test-helpers.ts';
import type { Item } from '#lib/data/types.ts';
import {
	badgeText,
	dueGroupOfDay,
	dueRows,
	dueSections,
	dueTag,
	dueTally,
	itemDueGroup,
	localDay
} from './due-reminders';

// Fixed instant at noon in the pre-setup day-grouping zone.
const TEST_ZONE = 'Europe/Oslo';
const NOW = new Date('2026-11-02T11:00:00.000Z');

describe('localDay', () => {
	it('uses the pre-setup Europe/Oslo zone across midnight', () => {
		expect(localDay(new Date('2026-01-05T22:59:00.000Z'))).toBe('2026-01-05');
		expect(localDay(new Date('2026-01-05T23:01:00.000Z'))).toBe('2026-01-06');
	});

	it('writes the configured local day as YYYY-MM-DD across midnight', () => {
		expect(localDay(NOW, TEST_ZONE)).toBe('2026-11-02');
		expect(localDay(new Date('2026-01-05T22:59:00.000Z'), TEST_ZONE)).toBe('2026-01-05');
		expect(localDay(new Date('2026-01-05T23:01:00.000Z'), TEST_ZONE)).toBe('2026-01-06');
	});
});

describe('dueGroupOfDay', () => {
	it('splits days into disjoint groups: overdue, today, tomorrow, days 2–7, later', () => {
		const groups = [
			'2026-10-31',
			'2026-11-02',
			'2026-11-03',
			'2026-11-04',
			'2026-11-09',
			'2026-11-10'
		].map((date) => dueGroupOfDay(date, '2026-11-02'));
		expect(groups).toEqual(['overdue', 'today', 'tomorrow', 'next7', 'next7', 'later']);
	});

	it('counts across a month and a year', () => {
		expect(dueGroupOfDay('2027-01-01', '2026-12-31')).toBe('tomorrow');
		expect(dueGroupOfDay('2026-12-31', '2027-01-01')).toBe('overdue');
	});
});

describe('itemDueGroup', () => {
	const list = makeList();
	it('leaves out done and undated items', () => {
		expect(itemDueGroup(makeItem(list.uid, { date: '2026-11-02', done: true }), NOW)).toBeNull();
		expect(itemDueGroup(makeItem(list.uid, { date: null }), NOW)).toBeNull();
		expect(itemDueGroup(makeItem(list.uid, { date: '2026-11-02' }), NOW)).toBe('today');
	});

	it('moves an item to the next group when the day rolls over', () => {
		const tomorrowItem = makeItem(list.uid, { date: '2026-11-03' });
		expect(itemDueGroup(tomorrowItem, NOW, TEST_ZONE)).toBe('tomorrow');
		expect(itemDueGroup(tomorrowItem, new Date('2026-11-02T23:01:00.000Z'), TEST_ZONE)).toBe(
			'today'
		);
	});
});

describe('dueTally', () => {
	const list = makeList();
	it('counts unchecked overdue, today and tomorrow items only', () => {
		const items: Item[] = [
			makeItem(list.uid, { date: '2026-10-30' }),
			makeItem(list.uid, { date: '2026-11-02' }),
			makeItem(list.uid, { date: '2026-11-03' }),
			makeItem(list.uid, { date: '2026-11-04' }),
			makeItem(list.uid, { date: '2026-11-20' }),
			makeItem(list.uid, { date: null }),
			makeItem(list.uid, { date: '2026-11-02', done: true })
		];
		expect(dueTally(items, NOW)).toEqual({ count: 3, overdue: 1 });
		expect(dueTally([], NOW)).toEqual({ count: 0, overdue: 0 });
	});
});

describe('badgeText', () => {
	it('shows the number, 99+ above 99', () => {
		expect(badgeText(7)).toBe('7');
		expect(badgeText(99)).toBe('99');
		expect(badgeText(100)).toBe('99+');
	});
});

describe('dueRows and dueSections', () => {
	const groceries = makeList({ name: 'Groceries' });
	const chores = makeList({ name: 'Chores' });
	const names = new Map([
		[groceries.uid, 'Groceries'],
		[chores.uid, 'Chores']
	]);
	const listName = (uid: string) => names.get(uid) ?? '';

	it('sorts by day, then list name, item name and UID', () => {
		const late = makeItem(groceries.uid, { name: 'bread', date: '2026-11-02' });
		const milk = makeItem(groceries.uid, { name: 'milk', date: '2026-11-02' });
		const dish = makeItem(chores.uid, { name: 'dishes', date: '2026-11-02' });
		const earlier = makeItem(chores.uid, { name: 'zeta', date: '2026-10-01' });
		const rows = dueRows([milk, dish, late, earlier], listName, NOW);
		// Earlier day first; on 2 Nov, Chores before Groceries, then by item name.
		expect(rows.map((row) => row.item.uid)).toEqual([earlier.uid, dish.uid, late.uid, milk.uid]);
		// Same day and name: the UID decides.
		const twin = makeItem(groceries.uid, { name: 'milk', date: '2026-11-02' });
		const twins = dueRows([twin, milk], listName, NOW).map((row) => row.item.uid);
		expect(twins).toEqual([...twins].sort());
	});

	it('shows each group once and skips the empty ones', () => {
		const list = groceries.uid;
		const rows = dueRows(
			[
				makeItem(list, { date: '2026-11-10' }),
				makeItem(list, { date: '2026-11-03' }),
				makeItem(list, { date: '2026-11-04' })
			],
			listName,
			NOW
		);
		expect(dueSections(rows).map((section) => section.group)).toEqual([
			'tomorrow',
			'next7',
			'later'
		]);
	});

	it('gives the date label color and words; later days have none', () => {
		expect(dueTag('overdue')).toEqual({ text: 'Overdue', tone: 'danger' });
		expect(dueTag('today')).toEqual({ text: 'Today', tone: 'warning' });
		expect(dueTag('tomorrow')).toEqual({ text: 'Tomorrow', tone: 'warning' });
		expect(dueTag('next7')).toBeNull();
		expect(dueTag('later')).toBeNull();
	});
});

describe('confirmed timed deadlines', () => {
	it('uses the instant for overdue strictly after it and for device-local grouping', () => {
		const deadline = new Date('2026-11-02T11:00:00.000Z');
		const item = makeItem('l', {
			date: '2026-11-03',
			due_time: '01:00',
			due_timezone: 'Pacific/Kiritimati',
			due_at: deadline.toISOString()
		});
		expect(itemDueGroup(item, new Date(deadline.valueOf() - 1), TEST_ZONE)).toBe('today');
		expect(itemDueGroup(item, deadline, TEST_ZONE)).toBe('today');
		expect(itemDueGroup(item, new Date(deadline.valueOf() + 1), TEST_ZONE)).toBe('overdue');
		expect(dueTally([item], new Date(deadline.valueOf() + 1), TEST_ZONE)).toEqual({
			count: 1,
			overdue: 1
		});
		expect(
			dueSections(dueRows([item], () => '', new Date(deadline.valueOf() + 1), TEST_ZONE))[0].group
		).toBe('overdue');
		expect(dueTag(itemDueGroup(item, new Date(deadline.valueOf() + 1), TEST_ZONE)!)?.text).toBe(
			'Overdue'
		);
	});
	it('uses the confirmed instant day rather than the wall date at device midnight', () => {
		const now = new Date('2026-11-02T22:00:00.000Z');
		const instant = new Date('2026-11-02T23:30:00.000Z');
		const item = makeItem('l', {
			date: '2026-11-02',
			due_time: '12:00',
			due_timezone: 'America/Adak',
			due_at: instant.toISOString()
		});
		expect(itemDueGroup(item, now, TEST_ZONE)).toBe('tomorrow');
		expect(itemDueGroup(item, new Date('2026-11-02T23:01:00.000Z'), TEST_ZONE)).toBe('today');
	});
	it('does not manufacture an instant for an unsynced wall intent', () => {
		const item = makeItem('l', {
			date: '2026-11-02',
			due_time: '01:00',
			due_timezone: 'Europe/Oslo',
			due_at: null
		});
		expect(itemDueGroup(item, NOW, TEST_ZONE)).toBe('today');
	});
});

it('uses the enrolled device zone for calendar grouping without changing overdue instants', () => {
	const now = new Date('2026-11-02T23:30:00Z');
	expect(localDay(now, 'Pacific/Kiritimati')).toBe('2026-11-03');
	expect(localDay(now, 'America/Adak')).toBe('2026-11-02');
	expect(
		itemDueGroup({ date: '2026-11-03', done: false, due_at: null }, now, 'Pacific/Kiritimati')
	).toBe('today');
	expect(
		itemDueGroup(
			{ date: '2026-11-03', done: false, due_at: '2026-11-02T23:00:00Z' },
			now,
			'Pacific/Kiritimati'
		)
	).toBe('overdue');
});
