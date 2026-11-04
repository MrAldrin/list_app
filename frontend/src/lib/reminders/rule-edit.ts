import { ruleToInput, type InputRule, type StoredRule } from './rules';

export type EditableRule =
	| { kind: 'relative'; amount: number; unit: 'minutes' | 'hours' | 'days' | 'weeks' }
	| {
			kind: 'fixed';
			date: string;
			time: string;
			timezone: string;
			original?: Extract<StoredRule, { kind: 'fixed' }>;
	  };

export function editStoredRule(rule: StoredRule): EditableRule {
	const input = ruleToInput(rule);
	if (input.kind === 'fixed' && rule.kind === 'fixed') return { ...input, original: rule };
	return input as EditableRule;
}
export function editableRuleInput(
	rule: EditableRule
): InputRule | { kind: 'relative'; amount: number; unit: 'hours' | 'weeks' } {
	if (rule.kind === 'relative') return { kind: rule.kind, amount: rule.amount, unit: rule.unit };
	const same =
		rule.original &&
		rule.date === rule.original.date &&
		rule.time === rule.original.time &&
		rule.timezone === rule.original.timezone;
	return {
		kind: 'fixed',
		date: rule.date,
		time: rule.time,
		timezone: rule.timezone,
		...(same ? { id: rule.original!.id } : {})
	};
}
/** Relative limits and duplicate normalization mirror the server; it remains authoritative. */
export function validateEditableRules(rules: EditableRule[]): string | null {
	const limits = { minutes: 525600, hours: 8760, days: 365, weeks: 52 };
	const keys = new Set<string>();
	for (const rule of rules) {
		if (rule.kind !== 'relative') continue;
		if (!Number.isSafeInteger(rule.amount) || rule.amount < 0 || rule.amount > limits[rule.unit])
			return `Use a whole number from 0 to ${limits[rule.unit]} for ${rule.unit}.`;
		const key =
			rule.amount === 0
				? 'at-due'
				: rule.unit === 'minutes' || rule.unit === 'hours'
					? `elapsed:${rule.amount * (rule.unit === 'hours' ? 60 : 1)}`
					: `calendar:${rule.amount * (rule.unit === 'weeks' ? 7 : 1)}`;
		if (keys.has(key)) return 'Duplicate relative rules are not allowed.';
		keys.add(key);
	}
	return null;
}
