// The clock the due views read. It moves on when the local day changes (checked
// every minute, and when the page is shown again), so labels and counts follow
// midnight without a reload. Browsers pause timers in background tabs, which the
// visibility check covers. It never moves within a day, so views do not redo work.

import { localDay } from './due-reminders.ts';

/** How often the clock checks for a new day, in milliseconds. */
export const DUE_CLOCK_CHECK_MS = 60_000;

let instant = new Date();
/** The local day of `instant`. Views read it, so a new day reruns them. */
let day = $state(localDay(instant));

/** The current time for the due views. Reading it in a `$derived` keeps the view up to date. */
export const dueClock = {
	get now(): Date {
		void day;
		return instant;
	}
};

/** Moves the clock to `next` when it is on another local day; otherwise nothing changes. */
export function advanceDueClock(next: Date): void {
	const nextDay = localDay(next);
	if (nextDay === day) return;
	instant = next;
	day = nextDay;
}

/** Checks the day now, every minute and when the page is shown again. Returns the function that stops it. */
export function startDueClock(): () => void {
	// A plain Date, not SvelteDate: the day is the reactive state, and SvelteDate ignores fake timers in tests.
	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	const check = () => advanceDueClock(new Date());
	check();
	const timer = setInterval(check, DUE_CLOCK_CHECK_MS);
	document.addEventListener('visibilitychange', check);
	return () => {
		clearInterval(timer);
		document.removeEventListener('visibilitychange', check);
	};
}
