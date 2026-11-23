import type * as Contract from '#lib/contracts/v1/reminders.ts';

export type StoredRule = typeof Contract.StoredRule.Type;
export type InputRule = typeof Contract.InputRule.Type;

/** Keep the fixed identity and wall intent, never submit the confirmed instant. */
export function ruleToInput(rule: StoredRule): InputRule {
	if (rule.kind === 'fixed') {
		return {
			kind: 'fixed',
			id: rule.id,
			date: rule.date,
			time: rule.time,
			timezone: rule.timezone
		};
	}
	return {
		kind: 'relative',
		amount: rule.amount,
		unit: rule.basis === 'calendar' ? 'days' : 'minutes'
	};
}
