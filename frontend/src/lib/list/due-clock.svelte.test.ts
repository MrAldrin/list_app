// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { advanceDueClock, dueClock, startDueClock } from './due-clock.svelte.ts';
import { localDay } from './due-reminders.ts';

describe('advanceDueClock', () => {
	it('moves within a day as well as across days', () => {
		advanceDueClock(new Date(2026, 10, 2, 12));
		expect(localDay(dueClock.now)).toBe('2026-11-02');

		advanceDueClock(new Date(2026, 10, 2, 20));
		expect(dueClock.now).toEqual(new Date(2026, 10, 2, 20));

		advanceDueClock(new Date(2026, 10, 3, 0, 1));
		expect(dueClock.now).toEqual(new Date(2026, 10, 3, 0, 1));
	});
});

describe('startDueClock', () => {
	let stop: (() => void) | undefined;

	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date(2026, 10, 4, 23, 59));
		advanceDueClock(new Date());
	});

	afterEach(() => {
		stop?.();
		stop = undefined;
		vi.useRealTimers();
	});

	it('checks the day at once, so a remount after midnight is not stale', () => {
		stop = startDueClock();
		stop();
		stop = undefined;

		vi.setSystemTime(new Date(2026, 10, 5, 0, 0));
		stop = startDueClock();
		expect(localDay(dueClock.now)).toBe('2026-11-05');
	});

	it('updates within a day when the minute timer runs', () => {
		vi.setSystemTime(new Date(2026, 10, 4, 12, 0));
		stop = startDueClock();
		vi.advanceTimersByTime(60_000);
		expect(dueClock.now).toEqual(new Date(2026, 10, 4, 12, 1));
	});

	it('checks every minute and when the page is shown again', () => {
		stop = startDueClock();

		vi.setSystemTime(new Date(2026, 10, 5, 0, 0));
		vi.advanceTimersByTime(60_000);
		expect(localDay(dueClock.now)).toBe('2026-11-05');

		vi.setSystemTime(new Date(2026, 10, 6, 9, 0));
		document.dispatchEvent(new Event('visibilitychange'));
		expect(localDay(dueClock.now)).toBe('2026-11-06');
	});

	it('stops the timer and the visibility check when stopped', () => {
		stop = startDueClock();
		stop();
		stop = undefined;
		const dayWhenStopped = localDay(dueClock.now);

		vi.setSystemTime(new Date(2026, 10, 7, 9, 0));
		vi.advanceTimersByTime(60_000);
		document.dispatchEvent(new Event('visibilitychange'));
		expect(localDay(dueClock.now)).toBe(dayWhenStopped);
	});
});
