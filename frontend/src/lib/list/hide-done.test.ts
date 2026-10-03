import { describe, expect, it } from 'vitest';
import type { HideDone } from '#lib/data/index.ts';
import { COUNT_WARNING, hideDoneChange, parseHideDoneCount } from './hide-done';

const settings = (overrides: Partial<HideDone> = {}): HideDone => ({
	mode: 'off',
	age_days: 7,
	recent_count: 10,
	...overrides
});

describe('parseHideDoneCount', () => {
	it('reads whole numbers from 0 to 100,000', () => {
		expect(parseHideDoneCount('0')).toBe(0);
		expect(parseHideDoneCount(' 12 ')).toBe(12);
		expect(parseHideDoneCount('100000')).toBe(100_000);
	});

	it('refuses blanks, fractions, negatives and too large numbers', () => {
		for (const text of ['', '  ', '1.5', '-1', '100001', 'abc', 'Infinity']) {
			expect(parseHideDoneCount(text)).toBeNull();
		}
	});

	it('has NiceGUI warning text', () => {
		expect(COUNT_WARNING).toBe('Enter a whole number between 0 and 100000.');
	});
});

describe('hideDoneChange', () => {
	it('turning hiding on picks "All", whatever mode was used before', () => {
		expect(hideDoneChange(settings(), { field: 'enabled', value: true })).toEqual({
			mode: 'all'
		});
	});

	it('turning hiding off sends only the mode, so the counts stay', () => {
		expect(hideDoneChange(settings({ mode: 'age' }), { field: 'enabled', value: false })).toEqual({
			mode: 'off'
		});
	});

	it('sends a new mode only when it changed', () => {
		const current = settings({ mode: 'all' });
		expect(hideDoneChange(current, { field: 'mode', value: 'recent' })).toEqual({
			mode: 'recent'
		});
		expect(hideDoneChange(current, { field: 'mode', value: 'all' })).toBeNull();
		expect(hideDoneChange(current, { field: 'mode', value: 'off' })).toBeNull();
	});

	it('sends one count only when it changed', () => {
		const current = settings({ mode: 'age' });
		expect(hideDoneChange(current, { field: 'age_days', value: 0 })).toEqual({ age_days: 0 });
		expect(hideDoneChange(current, { field: 'age_days', value: 7 })).toBeNull();
		expect(hideDoneChange(current, { field: 'recent_count', value: 3 })).toEqual({
			recent_count: 3
		});
	});

	it('does nothing when the switch already matches', () => {
		expect(hideDoneChange(settings(), { field: 'enabled', value: false })).toBeNull();
		expect(
			hideDoneChange(settings({ mode: 'recent' }), { field: 'enabled', value: true })
		).toBeNull();
	});
});
