import { describe, expect, it } from 'vitest';
import { connectionStatus, offlineNoticeText, savedTimeLabel, waitingChangesText } from './status';

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

describe('saved time label', () => {
	const now = new Date(2026, 9, 12, 20, 0);
	const today = new Date(2026, 9, 12, 18, 5).toISOString();
	const earlier = new Date(2026, 9, 10, 18, 5).toISOString();

	it('shows only the time for today', () => {
		expect(savedTimeLabel(today, now, 'en-GB')).toBe('18:05');
	});

	it('adds a short date for another day', () => {
		expect(savedTimeLabel(earlier, now, 'en-GB')).toBe('10 Oct, 18:05');
	});

	it('leaves the time out when missing or invalid', () => {
		expect(savedTimeLabel(null, now)).toBeNull();
		expect(savedTimeLabel('nope', now)).toBeNull();
	});
});

describe('offline notice text', () => {
	it('says that changes are saved on the phone', () => {
		expect(offlineNoticeText()).toBe('Offline — changes are saved on this phone.');
	});

	it('says how many changes wait to be sent', () => {
		expect(offlineNoticeText(2)).toBe('Offline — 2 changes waiting to be sent.');
	});

	it('counts waiting changes', () => {
		expect(waitingChangesText(0)).toBeNull();
		expect(waitingChangesText(1)).toBe('1 change waiting to be sent.');
		expect(waitingChangesText(3)).toBe('3 changes waiting to be sent.');
	});
});
