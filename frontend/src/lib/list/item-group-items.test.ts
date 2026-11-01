import { describe, expect, it } from 'vitest';
import {
	itemGroupSuggestions,
	MAX_GROUP_ITEM_COUNT,
	MAX_GROUP_ITEM_SUGGESTIONS
} from './item-group-items';

describe('itemGroupSuggestions', () => {
	it('suggests matching names from the supplied room data only', () => {
		expect(itemGroupSuggestions(['Coffee', 'Oat milk', 'Rice'], [], ' cof ')).toEqual(['Coffee']);
	});

	it('does not suggest blank text, names already in the group or duplicate room names', () => {
		expect(itemGroupSuggestions(['milk', 'Milk', 'oat milk', 'bread'], ['MILK'], 'mi')).toEqual([
			'oat milk'
		]);
		expect(itemGroupSuggestions(['milk'], [], '  ')).toEqual([]);
	});

	it('sorts names and limits the suggestions', () => {
		const names = ['tea five', 'tea four', 'tea three', 'tea two', 'tea one', 'tea zero'];
		expect(itemGroupSuggestions(names, [], 'tea')).toEqual([
			'tea five',
			'tea four',
			'tea one',
			'tea three',
			'tea two'
		]);
		expect(MAX_GROUP_ITEM_COUNT).toBe(1_000);
		expect(MAX_GROUP_ITEM_SUGGESTIONS).toBe(5);
	});
});
