import { describe, expect, it } from 'vitest';
import { connectionStatus } from './status';

describe('connectionStatus', () => {
	it('is null when the stream is open and nothing waits', () => {
		expect(connectionStatus({ live: 'open', queued: 0, retrying: false })).toBeNull();
		expect(connectionStatus({ live: 'stopped', queued: 0, retrying: false })).toBeNull();
	});

	it('says "Saving…" while writes wait or are retried', () => {
		const saving = { kind: 'saving', text: 'Saving…' };
		expect(connectionStatus({ live: 'open', queued: 2, retrying: false })).toEqual(saving);
		expect(connectionStatus({ live: 'open', queued: 1, retrying: true })).toEqual(saving);
	});

	it('says "Reconnecting…" while the stream is down, also with waiting writes', () => {
		const reconnecting = { kind: 'offline', text: 'Reconnecting…' };
		expect(connectionStatus({ live: 'reconnecting', queued: 0, retrying: false })).toEqual(
			reconnecting
		);
		expect(connectionStatus({ live: 'reconnecting', queued: 3, retrying: true })).toEqual(
			reconnecting
		);
	});

	it('says "Connecting…" before the first open', () => {
		expect(connectionStatus({ live: 'connecting', queued: 0, retrying: false })?.text).toBe(
			'Connecting…'
		);
	});
});
