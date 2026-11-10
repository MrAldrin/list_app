import { expect, it } from 'vitest';
import type { Item } from '#lib/data/index.ts';
import { makeItem, makeList } from '#lib/data/test-helpers.ts';
import { itemEditBase } from './items.ts';

const opened = makeItem(makeList().uid, { changed_seq: 5 });

it('uses the settled tag-only version without changing draft fields', () => {
	const tagged = { ...opened, tags: ['Shop'], changed_seq: 6 };
	expect(itemEditBase(opened, tagged)).toBe(tagged);
});

it.each([
	{ name: 'Other' },
	{ description: 'Someone else wrote this' },
	{ quantity: 2 },
	{ date: '2026-11-11' },
	{ due_time: '12:00' },
	{ due_timezone: 'UTC' },
	{ due_at: '2026-11-11T12:00:00Z' },
	{ done: true },
	{ completed_at: '2026-11-11T12:00:00Z' },
	{ add_count: 3 },
	{ added_at: '2026-11-11T12:00:00Z' },
	{ uid: 'another-item' },
	{ list_uid: 'another-list' }
] satisfies Partial<Item>[])(
	'keeps the opening conflict base when other data changes: %j',
	(changes) => {
		expect(itemEditBase(opened, { ...opened, ...changes, tags: ['Shop'], changed_seq: 6 })).toBe(
			opened
		);
	}
);

it('keeps the opening base when the item disappeared', () => {
	expect(itemEditBase(opened, undefined)).toBe(opened);
});
