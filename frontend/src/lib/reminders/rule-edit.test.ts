import { describe, expect, it } from 'vitest';
import { editableRuleInput, editStoredRule, validateEditableRules } from './rule-edit';

describe('policy rule editing', () => {
	it('retains only the fixed identity and wall intent when unchanged', () => {
		const original = {
			kind: 'fixed' as const,
			id: 'abc',
			date: '2020-01-01',
			time: '10:00',
			timezone: 'UTC',
			instant: '2020-01-01T10:00:00Z',
			activation: '2019-01-01T00:00:00Z'
		};
		const editable = editStoredRule(original);
		expect(editableRuleInput(editable)).toEqual({
			kind: 'fixed',
			id: 'abc',
			date: '2020-01-01',
			time: '10:00',
			timezone: 'UTC'
		});
		if (editable.kind !== 'fixed') throw new Error('expected fixed rule');
		expect(editableRuleInput({ ...editable, time: '11:00' })).toEqual({
			kind: 'fixed',
			date: '2020-01-01',
			time: '11:00',
			timezone: 'UTC'
		});
	});
	it('converts server normalized rules and checks strict limits and normalized duplicates', () => {
		expect(
			editStoredRule({ kind: 'relative', basis: 'elapsed', amount: 60, key: 'elapsed:60m' })
		).toEqual({ kind: 'relative', amount: 60, unit: 'minutes' });
		expect(
			validateEditableRules([
				{ kind: 'relative', amount: 1, unit: 'hours' },
				{ kind: 'relative', amount: 60, unit: 'minutes' }
			])
		).toMatch(/Duplicate/);
		expect(validateEditableRules([{ kind: 'relative', amount: 1.5, unit: 'days' }])).toMatch(
			/whole number/
		);
		expect(validateEditableRules([{ kind: 'relative', amount: 366, unit: 'days' }])).toMatch(/365/);
		expect(
			validateEditableRules([
				{ kind: 'relative', amount: 7, unit: 'days' },
				{ kind: 'relative', amount: 168, unit: 'hours' }
			])
		).toBeNull();
	});
});
