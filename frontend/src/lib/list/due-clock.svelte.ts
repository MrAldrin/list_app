// Due views refresh every minute and on visibility or remount, including timed deadlines.
// Browsers may pause timers in background tabs.

/** How often the clock checks for deadline and day changes, in milliseconds. */
export const DUE_CLOCK_CHECK_MS = 60_000;

let instant = new Date();
/** A reactive generation for the plain Date value. */
let generation = $state(0);

/** The current time for the due views. Reading it in a `$derived` keeps the view up to date. */
export const dueClock = {
	get now(): Date {
		void generation;
		return instant;
	}
};

/** Refresh even within a day: a confirmed deadline may have passed. */
export function advanceDueClock(next: Date): void {
	instant = next;
	generation = next.getTime();
}

/** Checks the time now, every minute and when the page is shown again. Returns the function that stops it. */
export function startDueClock(): () => void {
	// A plain Date supports fake timers; the generation supplies reactivity.
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
