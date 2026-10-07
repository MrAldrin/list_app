import { afterEach, describe, expect, it } from 'vitest';
import { checkApiVersion, compat, EXPECTED_API_VERSION, resetCompat } from './compat.svelte';

function headers(value?: string): Headers {
	const result = new Headers();
	if (value !== undefined) result.set('X-Api-Version', value);
	return result;
}

describe('checkApiVersion', () => {
	afterEach(resetCompat);

	it('accepts the expected version', () => {
		checkApiVersion(headers(String(EXPECTED_API_VERSION)));
		expect(compat.incompatible).toBe(false);
	});

	it.each([String(EXPECTED_API_VERSION + 1), '0', ' 99 '])('marks version %j as new', (value) => {
		checkApiVersion(headers(value));
		expect(compat.incompatible).toBe(true);
	});

	it('treats a missing or unreadable header as compatible', () => {
		checkApiVersion(headers());
		checkApiVersion(headers(''));
		checkApiVersion(headers('v2'));
		checkApiVersion(headers('1.5'));
		expect(compat.incompatible).toBe(false);
	});

	it('stays incompatible after a later matching answer', () => {
		checkApiVersion(headers('99'));
		checkApiVersion(headers(String(EXPECTED_API_VERSION)));
		expect(compat.incompatible).toBe(true);
	});
});
