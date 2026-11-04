/** Convert server-normalized rules to the private policy input contract. */
export type StoredRule =
	| { kind: 'relative'; basis: 'at_due' | 'elapsed' | 'calendar'; amount: number; key: string }
	| {
			kind: 'fixed';
			id: string;
			date: string;
			time: string;
			timezone: string;
			instant: string;
			activation: string;
	  };

export type InputRule =
	| { kind: 'relative'; amount: number; unit: 'minutes' | 'days' }
	| { kind: 'fixed'; id?: string; date: string; time: string; timezone: string };

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
