import { describe, expect, it } from 'vitest';
import { ruleToInput } from './rules';

describe('ruleToInput', () => {
	it('preserves elapsed and calendar meaning without sending server fields', () => {
		expect(
			ruleToInput({ kind: 'relative', basis: 'elapsed', amount: 1440, key: 'elapsed:1440m' })
		).toEqual({ kind: 'relative', amount: 1440, unit: 'minutes' });
		expect(
			ruleToInput({ kind: 'relative', basis: 'calendar', amount: 1, key: 'calendar:1d' })
		).toEqual({ kind: 'relative', amount: 1, unit: 'days' });
		expect(ruleToInput({ kind: 'relative', basis: 'at_due', amount: 0, key: 'at-due' })).toEqual({
			kind: 'relative',
			amount: 0,
			unit: 'minutes'
		});
	});
	it('keeps a fixed id and wall intent but omits confirmed server fields', () => {
		expect(
			ruleToInput({
				kind: 'fixed',
				id: 'saved-id',
				date: '2020-01-01',
				time: '09:00',
				timezone: 'Europe/Oslo',
				instant: 'instant',
				activation: 'activation'
			})
		).toEqual({
			kind: 'fixed',
			id: 'saved-id',
			date: '2020-01-01',
			time: '09:00',
			timezone: 'Europe/Oslo'
		});
	});
});
