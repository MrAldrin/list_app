import { describe, expect, it } from 'vitest';
import { canonicalTimeZone } from './time-zone';

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
