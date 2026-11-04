import { describe, expect, it } from 'vitest';
import { usableTimeZone } from './time-zone';

describe('usableTimeZone', () => {
	it('accepts supported IANA zones including UTC and non-hour offsets', () => {
		expect(usableTimeZone('UTC')).toBe(true);
		expect(usableTimeZone('Asia/Kathmandu')).toBe(true);
	});
	it('rejects empty, unavailable, offset-only and oversized values', () => {
		for (const zone of ['', 'Not/AZone', '+01:00', 'a'.repeat(65)])
			expect(usableTimeZone(zone)).toBe(false);
	});
});
