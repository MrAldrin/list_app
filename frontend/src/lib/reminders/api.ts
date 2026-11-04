import { Api } from '#lib/data/api.ts';
import { newId } from '#lib/data/ids.ts';

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

/** Private requests go directly to the server, never the shared offline queue. */
export class ReminderApi {
	private readonly base: string;
	constructor(
		slug: string,
		private readonly api = new Api()
	) {
		this.base = `/api/v1/rooms/${encodeURIComponent(slug)}/reminders`;
	}
	enrollment() {
		return this.api.request<{ enrollment: Enrollment }>('GET', `${this.base}/preferences`);
	}
	device() {
		return this.api.request<{ device: Device | null }>('GET', `${this.base}/preferences/device`);
	}
	prepare(
		method: PendingWrite['method'],
		path: 'enrollment' | 'preferences' | 'preferences/device',
		body: Record<string, unknown>
	): PendingWrite {
		return { method, path: `${this.base}/${path}`, body: { ...body, op_id: newId() } };
	}
	send<T>(write: PendingWrite): Promise<T> {
		return this.api.request<T>(write.method, write.path, write.body);
	}
}
