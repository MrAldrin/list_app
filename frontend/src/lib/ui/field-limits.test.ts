import { describe, expect, it } from 'vitest';
import { shortPasswordMessage } from './field-limits';

describe('shortPasswordMessage', () => {
	it('asks for 4 or more characters', () => {
		expect(shortPasswordMessage('abc')).toBe('Password must be at least 4 characters');
		expect(shortPasswordMessage('abcd')).toBeNull();
	});

	it('counts characters, not UTF-16 units', () => {
		expect(shortPasswordMessage('😀😀😀')).not.toBeNull();
		expect(shortPasswordMessage('😀😀😀😀')).toBeNull();
	});

	it('leaves blank passwords to the server', () => {
		expect(shortPasswordMessage('')).toBeNull();
		expect(shortPasswordMessage('   ')).toBeNull();
	});
});
