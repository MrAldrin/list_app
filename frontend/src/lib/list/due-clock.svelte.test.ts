import { describe, expect, it } from 'vitest';
import { advanceDueClock, dueClock } from './due-clock.svelte.ts';
import { localDay } from './due-reminders.ts';

describe('advanceDueClock', () => {
	it('moves on only when the local day changes', () => {
		advanceDueClock(new Date(2026, 10, 2, 12));
		expect(localDay(dueClock.now)).toBe('2026-11-02');

		advanceDueClock(new Date(2026, 10, 2, 20));
		expect(dueClock.now).toEqual(new Date(2026, 10, 2, 12));

		advanceDueClock(new Date(2026, 10, 3, 0, 1));
		expect(dueClock.now).toEqual(new Date(2026, 10, 3, 0, 1));
	});
});
