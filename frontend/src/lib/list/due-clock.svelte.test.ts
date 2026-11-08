// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { advanceDueClock, dueClock, startDueClock } from './due-clock.svelte.ts';
import { localDay } from './due-reminders.ts';

// Fixed UTC instants straddle midnight in the default Europe/Oslo zone.

describe('advanceDueClock', () => {
	it('moves within a day as well as across the default-zone day boundary', () => {
		const noon = new Date('2026-11-02T11:00:00.000Z');
		advanceDueClock(noon);
		expect(localDay(dueClock.now)).toBe('2026-11-02');

		const evening = new Date('2026-11-02T19:00:00.000Z');
		advanceDueClock(evening);
		expect(dueClock.now).toEqual(evening);

		const afterMidnight = new Date('2026-11-02T23:01:00.000Z');
		advanceDueClock(afterMidnight);
		expect(dueClock.now).toEqual(afterMidnight);
		expect(localDay(dueClock.now)).toBe('2026-11-03');
	});
});

describe('startDueClock', () => {
	let stop: (() => void) | undefined;

	beforeEach(() => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date('2026-11-04T22:59:00.000Z'));
		advanceDueClock(new Date());
	});

	afterEach(() => {
		stop?.();
		stop = undefined;
		vi.useRealTimers();
	});

	it('checks the day at once, so a remount after midnight is not stale', () => {
		stop = startDueClock();
		expect(localDay(dueClock.now)).toBe('2026-11-04');
		stop();
		stop = undefined;

		vi.setSystemTime(new Date('2026-11-04T23:00:00.000Z'));
		stop = startDueClock();
		expect(localDay(dueClock.now)).toBe('2026-11-05');
	});

	it('updates within a day when the minute timer runs', () => {
		vi.setSystemTime(new Date('2026-11-04T11:00:00.000Z'));
		stop = startDueClock();
		vi.advanceTimersByTime(60_000);
		expect(dueClock.now).toEqual(new Date('2026-11-04T11:01:00.000Z'));
	});

	it('checks every minute and when the page is shown again', () => {
		stop = startDueClock();

		vi.setSystemTime(new Date('2026-11-04T23:00:00.000Z'));
		vi.advanceTimersByTime(60_000);
		expect(localDay(dueClock.now)).toBe('2026-11-05');

		vi.setSystemTime(new Date('2026-11-05T23:00:00.000Z'));
		document.dispatchEvent(new Event('visibilitychange'));
		expect(localDay(dueClock.now)).toBe('2026-11-06');
	});

	it('stops the timer and the visibility check when stopped', () => {
		stop = startDueClock();
		stop();
		stop = undefined;
		const dayWhenStopped = localDay(dueClock.now);

		vi.setSystemTime(new Date('2026-11-05T23:00:00.000Z'));
		vi.advanceTimersByTime(60_000);
		document.dispatchEvent(new Event('visibilitychange'));
		expect(localDay(dueClock.now)).toBe(dayWhenStopped);
	});
});
