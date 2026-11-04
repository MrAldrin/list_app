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
}
export type PendingWrite = {
	method: 'POST' | 'PATCH';
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
		typeof value.paused === 'boolean'
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
		path: 'enrollment' | 'preferences' | 'preferences/device',
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
