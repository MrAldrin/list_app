import { describe, expect, it } from 'vitest';
import { validateData } from './snapshot-validate';

const identity = { kind: 'room' as const, slug: 'kitchen' };

function snapshot(list: Record<string, unknown>) {
	return {
		seq: 5,
		room: { slug: 'kitchen', name: 'Kitchen' },
		lists: [{ uid: 'list-1', slug: 'groceries', name: 'Groceries', tags: [], ...list }],
		items: []
	};
}

const hideDone = { mode: 'off', age_days: 7, recent_count: 10 };

describe('validateData: tag settings', () => {
	it('gives the defaults to a list saved before tag settings existed', () => {
		const data = validateData(identity, snapshot({ hide_done: hideDone, changed_seq: 3 }));
		expect(data?.lists[0].tag_settings).toEqual({
			mode: 'multi',
			show_on_items: true,
			only_item_tags: false,
			colors: {}
		});
	});

	it('keeps the stored tag settings', () => {
		const settings = {
			mode: 'single',
			show_on_items: false,
			only_item_tags: true,
			colors: { Lidl: 6 }
		};
		const data = validateData(
			identity,
			snapshot({ hide_done: hideDone, tag_settings: settings, changed_seq: 3 })
		);
		expect(data?.lists[0].tag_settings).toEqual(settings);
	});

	it('rejects tag settings with an unknown mode or a color out of range', () => {
		const bad = [
			{ mode: 'many', show_on_items: true, only_item_tags: false, colors: {} },
			{ mode: 'multi', show_on_items: true, only_item_tags: false, colors: { a: 7 } }
		];
		for (const tag_settings of bad) {
			expect(
				validateData(identity, snapshot({ hide_done: hideDone, tag_settings, changed_seq: 3 }))
			).toBeNull();
		}
	});
});
