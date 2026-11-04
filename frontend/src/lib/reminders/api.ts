import { Api } from '#lib/data/api.ts';
import { newId } from '#lib/data/ids.ts';
import { ApiError } from '#lib/data/types.ts';

export type Mode = 'quiet' | 'daily_summary' | 'scheduled' | 'custom';
export type Enrollment =
	| { state: 'not_enrolled'; revision: null }
	| {
			state: 'active' | 'needs_resume' | 'opted_out';
			mode: Mode;
			summary_time: string;
			revision: number;
			activated_at: string | null;
	  };
export interface Device {
	revision: number;
	timezone: string;
	all_day_time: string;
	paused: boolean;
	quiet_hours: { start: string; end: string } | null;
	daily_cap: number;
	spacing_minutes: number;
	content_privacy: 'generic' | 'counts' | 'names';
	overdue_repeat_days: number | null;
}
export type PendingWrite = {
	method: 'POST' | 'PATCH' | 'PUT';
	path: string;
	body: Record<string, unknown>;
};

/** A write may have committed even though its successful response was unusable. */
export class UnknownWriteOutcome extends Error {}

function record(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function revision(value: unknown): value is number {
	return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}
function clock(value: unknown): value is string {
	return typeof value === 'string' && /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
}
function enrollment(value: unknown): value is Enrollment {
	if (!record(value)) return false;
	if (value.state === 'not_enrolled') return value.revision === null;
	return (
		(value.state === 'active' || value.state === 'needs_resume' || value.state === 'opted_out') &&
		(value.mode === 'quiet' ||
			value.mode === 'daily_summary' ||
			value.mode === 'scheduled' ||
			value.mode === 'custom') &&
		clock(value.summary_time) &&
		revision(value.revision) &&
		(typeof value.activated_at === 'string' || value.activated_at === null)
	);
}
function device(value: unknown): value is Device {
	return (
		record(value) &&
		revision(value.revision) &&
		typeof value.timezone === 'string' &&
		value.timezone.length > 0 &&
		clock(value.all_day_time) &&
		typeof value.paused === 'boolean' &&
		(value.quiet_hours === null ||
			(record(value.quiet_hours) &&
				clock(value.quiet_hours.start) &&
				clock(value.quiet_hours.end) &&
				value.quiet_hours.start !== value.quiet_hours.end)) &&
		typeof value.daily_cap === 'number' &&
		Number.isSafeInteger(value.daily_cap) &&
		value.daily_cap >= 1 &&
		value.daily_cap <= 50 &&
		typeof value.spacing_minutes === 'number' &&
		Number.isSafeInteger(value.spacing_minutes) &&
		value.spacing_minutes >= 1 &&
		value.spacing_minutes <= 60 &&
		(value.content_privacy === 'generic' ||
			value.content_privacy === 'counts' ||
			value.content_privacy === 'names') &&
		(value.overdue_repeat_days === null ||
			(typeof value.overdue_repeat_days === 'number' &&
				Number.isSafeInteger(value.overdue_repeat_days) &&
				value.overdue_repeat_days >= 1 &&
				value.overdue_repeat_days <= 30))
	);
}

/** Private requests go directly to the server, never the shared offline queue. */
export class ReminderApi {
	private readonly base: string;
	constructor(
		slug: string,
		private readonly api = new Api()
	) {
		this.base = `/api/v1/rooms/${encodeURIComponent(slug)}/reminders`;
	}
	async enrollment(): Promise<{ enrollment: Enrollment }> {
		const result = await this.api.request<unknown>('GET', `${this.base}/preferences`);
		if (!record(result) || !enrollment(result.enrollment))
			throw new Error('Could not read reminder enrollment.');
		return { enrollment: result.enrollment };
	}
	async device(): Promise<{ device: Device | null }> {
		const result = await this.api.request<unknown>('GET', `${this.base}/preferences/device`);
		if (!record(result) || (result.device !== null && !device(result.device)))
			throw new Error('Could not read device settings.');
		return { device: result.device as Device | null };
	}
	prepare(
		method: PendingWrite['method'],
		path: string,
		body: Record<string, unknown>
	): PendingWrite {
		return { method, path: `${this.base}/${path}`, body: { ...body, op_id: newId() } };
	}
	private async write(write: PendingWrite): Promise<unknown> {
		try {
			return await this.api.request<unknown>(write.method, write.path, write.body);
		} catch (error) {
			if (error instanceof ApiError && error.status >= 200 && error.status < 300)
				throw new UnknownWriteOutcome();
			throw error;
		}
	}
	async policy(path: string): Promise<PolicyResult> {
		const result = await this.api.request<unknown>('GET', `${this.base}/${path}`);
		if (!policyResult(result) || result.policy.scope !== policyScope(path))
			throw new Error('Could not read policy.');
		return result;
	}
	async sendPolicy(write: PendingWrite): Promise<PolicyResult> {
		const result = await this.write(write);
		if (
			!policyResult(result) ||
			result.policy.scope !== policyScope(write.path) ||
			result.policy.revision < 1
		)
			throw new UnknownWriteOutcome();
		return result;
	}
	async preview(itemUid: string, draft: Record<string, unknown> | null): Promise<Preview> {
		const result = await this.api.request<unknown>('POST', `${this.base}/preview`, {
			item_uid: itemUid,
			draft
		});
		if (!preview(result)) throw new Error('Could not read preview.');
		return result;
	}
	async sendEnrollment(write: PendingWrite): Promise<Enrollment> {
		const result = await this.write(write);
		if (
			!record(result) ||
			!enrollment(result.enrollment) ||
			result.enrollment.state === 'not_enrolled'
		)
			throw new UnknownWriteOutcome();
		return result.enrollment;
	}
	async sendDevice(write: PendingWrite): Promise<Device> {
		const result = await this.write(write);
		if (!record(result) || !device(result.device)) throw new UnknownWriteOutcome();
		return result.device;
	}
}

export type PolicyScope = 'room' | 'list' | 'item';
export interface Policy {
	scope: PolicyScope;
	state: 'inherit' | 'off' | 'replace';
	preset: Mode | null;
	summary_enabled: boolean;
	rules: import('./rules').StoredRule[];
	revision: number;
	activated_at: string | null;
}
export interface PolicyResult {
	policy: Policy;
	effective: Policy;
}
export interface Preview {
	source: PolicyScope;
	state: Policy['state'];
	preset: Mode | null;
	timezone: string;
	disabled_reasons: string[];
	provisional_fixed_ids: string[];
	entries: {
		kind: 'rules' | 'summary';
		instant: string;
		keys: string[];
		deferred_until: string | null;
		local_day: string | null;
	}[];
}
function policyScope(path: string): PolicyScope {
	return path.includes('/lists/') || path.startsWith('lists/')
		? 'list'
		: path.includes('/items/') || path.startsWith('items/')
			? 'item'
			: 'room';
}
function instant(value: unknown): value is string {
	return (
		typeof value === 'string' &&
		/^\d{4}-\d{2}-\d{2}T.*Z$/.test(value) &&
		Number.isFinite(Date.parse(value))
	);
}
function strings(value: unknown): value is string[] {
	return Array.isArray(value) && value.every((x) => typeof x === 'string');
}
function storedRule(value: unknown): value is import('./rules').StoredRule {
	if (!record(value)) return false;
	if (value.kind === 'relative')
		return (
			(value.basis === 'at_due' || value.basis === 'elapsed' || value.basis === 'calendar') &&
			typeof value.amount === 'number' &&
			Number.isSafeInteger(value.amount) &&
			value.amount >= 0 &&
			(value.basis === 'at_due'
				? value.amount === 0 && value.key === 'at-due'
				: value.amount > 0 &&
					value.key === `${value.basis}:${value.amount}${value.basis === 'elapsed' ? 'm' : 'd'}`)
		);
	return (
		value.kind === 'fixed' &&
		typeof value.id === 'string' &&
		/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(value.id) &&
		typeof value.date === 'string' &&
		/^\d{4}-\d{2}-\d{2}$/.test(value.date) &&
		clock(value.time) &&
		typeof value.timezone === 'string' &&
		value.timezone.length > 0 &&
		instant(value.instant) &&
		instant(value.activation)
	);
}
function policy(value: unknown): value is Policy {
	return (
		record(value) &&
		(value.scope === 'room' || value.scope === 'list' || value.scope === 'item') &&
		(value.state === 'inherit' || value.state === 'off' || value.state === 'replace') &&
		(value.preset === null ||
			value.preset === 'quiet' ||
			value.preset === 'daily_summary' ||
			value.preset === 'scheduled' ||
			value.preset === 'custom') &&
		typeof value.summary_enabled === 'boolean' &&
		Array.isArray(value.rules) &&
		value.rules.length <= 5 &&
		value.rules.every(storedRule) &&
		typeof value.revision === 'number' &&
		Number.isSafeInteger(value.revision) &&
		value.revision >= 0 &&
		(value.activated_at === null || instant(value.activated_at)) &&
		(value.state === 'replace'
			? value.preset !== null
			: value.preset === null && value.rules.length === 0 && !value.summary_enabled)
	);
}
function policyResult(value: unknown): value is PolicyResult {
	return record(value) && policy(value.policy) && policy(value.effective);
}
function preview(value: unknown): value is Preview {
	return (
		record(value) &&
		(value.source === 'room' || value.source === 'list' || value.source === 'item') &&
		(value.state === 'inherit' || value.state === 'off' || value.state === 'replace') &&
		(value.preset === null ||
			value.preset === 'quiet' ||
			value.preset === 'daily_summary' ||
			value.preset === 'scheduled' ||
			value.preset === 'custom') &&
		typeof value.timezone === 'string' &&
		strings(value.disabled_reasons) &&
		strings(value.provisional_fixed_ids) &&
		Array.isArray(value.entries) &&
		value.entries.length <= 5 &&
		value.entries.every(
			(e) =>
				record(e) &&
				(e.kind === 'rules' || e.kind === 'summary') &&
				instant(e.instant) &&
				strings(e.keys) &&
				(e.deferred_until === null || instant(e.deferred_until)) &&
				(e.local_day === null || typeof e.local_day === 'string')
		)
	);
}
