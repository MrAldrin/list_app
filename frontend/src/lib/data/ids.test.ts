import { describe, expect, it } from 'vitest';
import { newId } from './ids';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

describe('newId', () => {
	it('uses crypto.randomUUID when it exists (secure context)', () => {
		const fake = {
			randomUUID: () => '11111111-2222-4333-8444-555555555555',
			getRandomValues: () => {
				throw new Error('not used');
			}
		};
		expect(newId(fake as unknown as Crypto)).toBe('11111111-2222-4333-8444-555555555555');
	});

	it('falls back to getRandomValues without randomUUID (plain HTTP)', () => {
		// A secure context's crypto without randomUUID, as on plain HTTP.
		const insecure = { getRandomValues: crypto.getRandomValues.bind(crypto) };
		const ids = new Set(Array.from({ length: 200 }, () => newId(insecure)));
		expect(ids.size).toBe(200);
		for (const id of ids) expect(id).toMatch(UUID_V4);
	});

	it('sets the version and variant bits in the fallback', () => {
		const allOnes = {
			getRandomValues: <T extends ArrayBufferView>(array: T) => {
				new Uint8Array(array.buffer).fill(0xff);
				return array;
			}
		};
		expect(newId(allOnes as Crypto)).toBe('ffffffff-ffff-4fff-bfff-ffffffffffff');
	});

	it('makes UUID v4 strings by default', () => {
		expect(newId()).toMatch(UUID_V4);
	});
});
