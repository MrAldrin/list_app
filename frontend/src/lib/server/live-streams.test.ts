import { afterEach, expect, it, vi } from 'vitest';
import { EventFrame } from '#lib/contracts/v1/feed.ts';
import { apiError } from './api';
import { liveStream, wakeRoomStreams } from './live-streams';

const events = { status: 200, response: EventFrame };
const decoder = new TextDecoder();

afterEach(() => vi.useRealTimers());

it('coalesces wakes, suppresses unchanged cursors and accepts a lower cursor', async () => {
	vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] });
	let seq = 7;
	const read = vi.fn(async () => ({ roomId: 5, seq }));
	const response = await liveStream(events, new Request('http://local.test/events'), read);
	const reader = response.body!.getReader();
	try {
		expect(decoder.decode((await reader.read()).value)).toBe('event: seq\ndata: {"seq":7}\n\n');
		seq = 8;
		wakeRoomStreams(5);
		seq = 9;
		wakeRoomStreams(5);
		expect(decoder.decode((await reader.read()).value)).toBe('event: seq\ndata: {"seq":9}\n\n');

		const next = reader.read();
		wakeRoomStreams(5);
		await vi.advanceTimersByTimeAsync(5_000);
		expect(decoder.decode((await next).value)).toBe(':ping\n\n');
		seq = 1;
		wakeRoomStreams(4);
		expect(read).toHaveBeenCalledTimes(4);
		wakeRoomStreams(5);
		expect(decoder.decode((await reader.read()).value)).toBe('event: seq\ndata: {"seq":1}\n\n');
	} finally {
		await reader.cancel();
	}
});

it.each([401, 503])(
	'rechecks idle access and closes on %s without a false revocation',
	async (status) => {
		vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] });
		const read = vi.fn(async () => ({ roomId: 5, seq: 1 }));
		const response = await liveStream(events, new Request('http://local.test/events'), read);
		const reader = response.body!.getReader();
		try {
			expect((await reader.read()).done).toBe(false);
			read.mockRejectedValue(
				apiError(status, status === 401 ? 'not_authenticated' : 'unavailable')
			);
			for (let beat = 0; beat < 2; beat += 1) {
				const ping = reader.read();
				await vi.advanceTimersByTimeAsync(5_000);
				expect(decoder.decode((await ping).value)).toBe(':ping\n\n');
			}
			const recheck = reader.read();
			await vi.advanceTimersByTimeAsync(5_000);
			if (status === 401) {
				expect(decoder.decode((await recheck).value)).toBe('event: revoked\ndata: {}\n\n');
				expect((await reader.read()).done).toBe(true);
			} else expect((await recheck).done).toBe(true);
			expect(read).toHaveBeenCalledTimes(3);
		} finally {
			await reader.cancel();
		}
	}
);
