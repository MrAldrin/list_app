import type { InputRule, Policy } from '#lib/contracts/v1/reminders.ts';
import { instantText, wallInstant } from './zoned-time';

export type PolicyView = typeof Policy.Type;
export type Rule = PolicyView['rules'][number];
type Relative = Extract<Rule, { kind: 'relative' }>;
type Fixed = Extract<Rule, { kind: 'fixed' }>;
export type PolicyDraft = {
	state: PolicyView['state'];
	preset?: PolicyView['preset'];
	rules?: readonly (typeof InputRule.Type)[];
	summary_enabled?: boolean;
};

export function relativeRule(basis: Relative['basis'], amount: number): Relative {
	const key =
		basis === 'at_due'
			? 'at-due'
			: basis === 'elapsed'
				? `elapsed:${amount}m`
				: `calendar:${amount}d`;
	return { kind: 'relative', basis, amount, key };
}

export function presetRules(preset: PolicyView['preset']): Rule[] {
	return preset === 'scheduled' ? [relativeRule('calendar', 1), relativeRule('at_due', 0)] : [];
}

function normalizeRules(
	inputs: NonNullable<PolicyDraft['rules']>,
	stored: readonly Rule[],
	now: Temporal.Instant,
	newId: () => string
): Rule[] {
	const byId = new Map(stored.filter((r): r is Fixed => r.kind === 'fixed').map((r) => [r.id, r]));
	const reserved = new Set<string>();
	for (const rule of inputs) {
		if (rule.kind !== 'fixed' || rule.id === undefined) continue;
		if (!byId.has(rule.id)) throw new Error('Unknown fixed reminder id');
		if (reserved.has(rule.id)) throw new Error('A fixed reminder id may be used once');
		reserved.add(rule.id);
	}
	const seen = new Set<string>();
	return inputs.map((input): Rule => {
		let rule: Rule;
		if (input.kind === 'relative') {
			const { amount, unit } = input;
			rule =
				amount === 0
					? relativeRule('at_due', 0)
					: unit === 'hours' || unit === 'minutes'
						? relativeRule('elapsed', amount * (unit === 'hours' ? 60 : 1))
						: relativeRule('calendar', amount * (unit === 'weeks' ? 7 : 1));
		} else {
			const { date, time, timezone, id } = input;
			const sameWall = (old: Fixed) =>
				old.date === date && old.time === time && old.timezone === timezone;
			const old = id
				? byId.get(id)
				: [...byId.values()].find((r) => !reserved.has(r.id) && sameWall(r));
			if (old && sameWall(old)) {
				reserved.add(old.id);
				rule = old;
			} else {
				const instant = wallInstant(Temporal.PlainDate.from(date), time, timezone);
				if (Temporal.Instant.compare(instant, now) <= 0)
					throw new Error('A new or changed fixed reminder must be in the future');
				rule = {
					kind: 'fixed',
					id: newId(),
					date,
					time,
					timezone,
					instant: instantText(instant),
					activation: instantText(now)
				};
			}
		}
		const key = rule.kind === 'relative' ? rule.key : `fixed:${rule.instant}`;
		if (seen.has(key))
			throw new Error(
				rule.kind === 'relative'
					? 'Duplicate relative reminder'
					: 'Two fixed reminders resolve to the same time'
			);
		seen.add(key);
		return rule;
	});
}

export function draftPolicy(
	draft: PolicyDraft,
	current: PolicyView,
	now: Temporal.Instant,
	newId = () => crypto.randomUUID() as string
): PolicyView {
	const { state, preset = null, rules = [], summary_enabled = false } = draft;
	const policy = { ...current, state, preset, summary_enabled: false, rules: [] as Rule[] };
	if (state !== 'replace') {
		if (preset !== null || rules.length || summary_enabled)
			throw new Error('Off/inherit takes no preset, rules or summary');
		return policy;
	}
	if (preset === null) throw new Error('A replacement requires a preset');
	if (preset === 'custom')
		return { ...policy, summary_enabled, rules: normalizeRules(rules, current.rules, now, newId) };
	if (rules.length || summary_enabled)
		throw new Error('Only custom accepts rules and summary_enabled');
	return { ...policy, summary_enabled: preset === 'daily_summary', rules: presetRules(preset) };
}

export function samePolicy(a: PolicyView, b: PolicyView): boolean {
	// Normalization excludes duplicates. For fixed rules the ID changes iff the
	// wall intent changes. Reordering alone is a semantic no-op.
	const identity = (rule: Rule) => (rule.kind === 'fixed' ? `fixed:${rule.id}` : rule.key);
	const aRules = new Set(a.rules.map(identity));
	return (
		a.state === b.state &&
		a.preset === b.preset &&
		a.summary_enabled === b.summary_enabled &&
		a.rules.length === b.rules.length &&
		b.rules.every((r) => aRules.has(identity(r)))
	);
}
