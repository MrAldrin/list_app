// Retry pauses shared by live-update reconnects, access revalidation and
// write retries. Each pause is in milliseconds; the last one repeats.

export const BACKOFF_DELAYS: readonly number[] = [1_000, 2_000, 5_000, 10_000, 30_000];

/** The pause before retry number `attempt` (counted from 0) in `delays`. */
export function backoffDelay(delays: readonly number[], attempt: number): number {
	return delays[Math.min(attempt, delays.length - 1)];
}
