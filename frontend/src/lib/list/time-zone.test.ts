import { describe, expect, it } from 'vitest';
import { DEFAULT_TIME_ZONE, validTime, canonicalTimeZone } from './time-zone';
import { localDay } from './due-reminders';

describe('reminder time and zone defaults', () => {
	it('accepts only 24-hour HH:MM', () => {
		for (const value of ['00:00', '09:05', '23:59']) expect(validTime(value)).toBe(true);
		for (const value of ['', '9:05', '24:00', '12:60', '01:00 PM'])
			expect(validTime(value)).toBe(false);
	});
	it('uses Oslo calendar days before setup and keeps explicitly supplied zones', () => {
		const instant = new Date('2026-01-01T23:30:00Z');
		expect(DEFAULT_TIME_ZONE).toBe('Europe/Oslo');
		expect(localDay(instant)).toBe('2026-01-02');
		expect(localDay(instant, 'America/New_York')).toBe('2026-01-01');
	});
});

describe('canonicalTimeZone', () => {
	it('accepts supported IANA zones including UTC and non-hour offsets', () => {
		expect(canonicalTimeZone('UTC')).toBe('UTC');
		expect(canonicalTimeZone('utc')).toBe('UTC');
		expect(canonicalTimeZone('europe/oslo')).toBe('Europe/Oslo');
		expect(canonicalTimeZone('eUROPE/oSLO')).toBe('Europe/Oslo');
		expect(canonicalTimeZone('Asia/Kathmandu')).not.toBeNull();
	});
	it('rejects empty, unavailable, offset-only and oversized values', () => {
		for (const zone of ['', 'Not/AZone', '+01:00', 'a'.repeat(65)])
			expect(canonicalTimeZone(zone)).toBeNull();
	});
});
