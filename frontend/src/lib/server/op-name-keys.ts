// Existing databases record algorithm 1 and Unicode 15.1. Bun's built-in
// lowercase uses newer tables. Never mix versions in a persisted key column.
import simpleLower from '@unicode/unicode-15.1.0/Simple_Case_Mapping/Lowercase/symbols.mjs';
import specialLower from '@unicode/unicode-15.1.0/Special_Casing/Lowercase/symbols.mjs';
import ignorable from '@unicode/unicode-15.1.0/Binary_Property/Case_Ignorable/regex.mjs';
import cased from '@unicode/unicode-15.1.0/Binary_Property/Cased/regex.mjs';
import commonFold from '@unicode/unicode-15.1.0/Case_Folding/C/symbols.mjs';
import fullFold from '@unicode/unicode-15.1.0/Case_Folding/F/symbols.mjs';
import { trimItemName } from '#lib/data/overlay.ts';

export function itemNameKey(name: string) {
	const chars = Array.from(trimItemName(name));
	function adjacentCased(i: number, step: number) {
		while (chars[i] && ignorable.test(chars[i])) i += step;
		return !!chars[i] && cased.test(chars[i]);
	}
	return chars
		.map((c, i) =>
			c === 'Σ' && adjacentCased(i - 1, -1) && !adjacentCased(i + 1, 1)
				? 'ς'
				: (specialLower.get(c) ?? simpleLower.get(c) ?? c)
		)
		.join('');
}
export function listKey(name: string) {
	return Array.from(trimItemName(name), (c) => fullFold.get(c) ?? commonFold.get(c) ?? c).join('');
}
