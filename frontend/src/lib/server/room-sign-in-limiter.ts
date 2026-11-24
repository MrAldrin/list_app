const WINDOW_MS = 60_000;
const ROOM_LIMIT = 10;
const GLOBAL_LIMIT = 30;

type Attempt = { readonly slug: string; readonly time: number };
type Reservation = { readonly release: () => void } | { readonly retryAfter: number };

// One chronological list enforces both limits. Even random slugs cannot make
// it grow past GLOBAL_LIMIT, and removing a reservation frees both slots.
export class RoomSignInLimiter {
	private attempts: Attempt[] = [];

	constructor(private readonly now: () => number = () => performance.now()) {}

	reserve(slug: string): Reservation {
		const time = this.now();
		this.attempts = this.attempts.filter((attempt) => time - attempt.time < WINDOW_MS);
		const room = this.attempts.filter((attempt) => attempt.slug === slug);
		const thresholds = [room.at(-ROOM_LIMIT), this.attempts.at(-GLOBAL_LIMIT)];
		const wait = Math.max(
			...thresholds.map((attempt) => (attempt ? attempt.time + WINDOW_MS - time : 0))
		);
		if (wait > 0) return { retryAfter: Math.ceil(wait / 1000) };
		const attempt = { slug, time };
		this.attempts.push(attempt);
		return {
			release: () => {
				const index = this.attempts.indexOf(attempt);
				if (index !== -1) this.attempts.splice(index, 1);
			}
		};
	}
}
