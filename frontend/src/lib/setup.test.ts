import { describe, expect, it } from 'vitest';

// A first test that only proves Vitest runs. Real tests (for the data layer)
// sit next to the code they test, as `*.test.ts` files.
describe('test setup', () => {
	it('runs Vitest', () => {
		expect(1 + 1).toBe(2);
	});
});
