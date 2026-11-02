import { describe, expect, it } from 'vitest';
import { makeItem, makeList } from '#lib/data/test-helpers.ts';
import type { Item } from '#lib/data/types.ts';
import { DueReminders, dueItems, dueSummary, localDay } from './due-reminders';

// Local noon on 2 Nov 2026, so time zones do not shift the day.
const NOW = new Date(2026, 10, 2, 12, 0);

describe('localDay', () => {
	it('writes the local day as YYYY-MM-DD', () => {
		expect(localDay(NOW)).toBe('2026-11-02');
		expect(localDay(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05');
	});
});

describe('dueItems', () => {
	const list = makeList();
	const item = (date: string | null, done = false) => makeItem(list.uid, { date, done });

	it('keeps unchecked items due tomorrow or earlier, overdue included', () => {
		const overdue = item('2026-10-30');
		const today = item('2026-11-02');
		const tomorrow = item('2026-11-03');
		const later = item('2026-11-04');
		const undated = item(null);
		const checked = item('2026-11-02', true);
		expect(dueItems([overdue, today, tomorrow, later, undated, checked], NOW)).toEqual([
			overdue,
			today,
			tomorrow
		]);
	});

	it('crosses the end of a month and year', () => {
		const newYearsEve = new Date(2026, 11, 31, 12);
		expect(dueItems([item('2027-01-01'), item('2027-01-02')], newYearsEve)).toHaveLength(1);
	});
});

describe('dueSummary', () => {
	const list = makeList();
	it('counts overdue, today and tomorrow', () => {
		const due = ['2026-11-01', '2026-11-02', '2026-11-02', '2026-11-03'].map((date) =>
			makeItem(list.uid, { date })
		);
		expect(dueSummary(due, NOW)).toBe('4 items due: 1 overdue, 2 today, 1 tomorrow');
		expect(dueSummary(due.slice(3), NOW)).toBe('1 item due: 1 tomorrow');
	});
});

describe('DueReminders', () => {
	const groceries = makeList({ name: 'Groceries' });
	const chores = makeList({ name: 'Chores' });
	function setup(items: Item[]) {
		const itemsOf = (uid: string) => items.filter((item) => item.list_uid === uid);
		return { items, itemsOf, lists: [groceries, chores] };
	}

	it('reminds every time a list opens, but the all-lists check only once per item', () => {
		const milk = makeItem(groceries.uid, { date: '2026-11-02' });
		const { itemsOf, lists } = setup([milk]);
		const reminders = new DueReminders();
		expect(reminders.listOpened(itemsOf(groceries.uid), NOW)).toEqual({
			message: '1 item due: 1 today',
			kind: 'warning'
		});
		expect(reminders.checkAll(lists, itemsOf, NOW)).toBeNull();
		expect(reminders.listOpened(itemsOf(groceries.uid), NOW)).not.toBeNull();
	});

	it('names the list, or each list with a count', () => {
		const { itemsOf, lists } = setup([
			makeItem(groceries.uid, { date: '2026-11-03' }),
			makeItem(chores.uid, { date: '2026-10-01' }),
			makeItem(chores.uid, { date: '2026-11-02' })
		]);
		expect(new DueReminders().checkAll(lists, itemsOf, NOW)).toEqual({
			message: 'Due soon: Groceries (1), Chores (2)',
			kind: 'danger'
		});
		expect(new DueReminders().checkAll([groceries], itemsOf, NOW)?.message).toBe(
			'Groceries: 1 item due: 1 tomorrow'
		);
	});

	it('reminds again when a new item becomes due or an item gets a new date', () => {
		const items = [makeItem(groceries.uid, { date: '2026-11-05' })];
		const { itemsOf, lists } = setup(items);
		const reminders = new DueReminders();
		expect(reminders.checkAll(lists, itemsOf, NOW)).toBeNull();
		// Two days later, the same item is due tomorrow.
		expect(reminders.checkAll(lists, itemsOf, new Date(2026, 10, 4, 9))).not.toBeNull();
		items[0] = { ...items[0], date: '2026-11-03' };
		expect(reminders.checkAll(lists, itemsOf, NOW)).not.toBeNull();
		items.push(makeItem(chores.uid, { date: '2026-11-02' }));
		expect(reminders.checkAll(lists, itemsOf, NOW)?.message).toBe('Chores: 1 item due: 1 today');
	});

	it('says nothing when nothing is due', () => {
		const { itemsOf, lists } = setup([makeItem(groceries.uid, { date: null })]);
		const reminders = new DueReminders();
		expect(reminders.listOpened(itemsOf(groceries.uid), NOW)).toBeNull();
		expect(reminders.checkAll(lists, itemsOf, NOW)).toBeNull();
	});
});
