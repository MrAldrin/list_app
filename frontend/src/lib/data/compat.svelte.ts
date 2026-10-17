// Does this page still match the server? The server sends its API version on
// every API answer (docs/api.md, "API version"). A different number means a
// deploy replaced the server while this page was open. Then writes stop and
// the page offers a reload. Nothing reloads by itself.

import { SvelteMap } from 'svelte/reactivity';

/**
 * The API version this build was made for. The server keeps the same number in
 * `src/api/version.py`; a Python test checks that both match.
 */
export const EXPECTED_API_VERSION = 2;

export const API_VERSION_HEADER = 'X-Api-Version';

export const INCOMPATIBLE_CODE = 'incompatible_version';
export const INCOMPATIBLE_MESSAGE = 'A new version is available. Reload to keep making changes.';

class Compat {
	/** True from the first answer with another version until the page reloads. */
	incompatible = $state(false);

	/** Unsent writes per open write queue, and whether the device keeps them. */
	readonly #waiting = new SvelteMap<object, { count: number; durable: boolean }>();

	/** Unsent writes, summed over every open queue. */
	get waitingWrites(): number {
		return this.#sum(() => true);
	}

	/** Unsent writes that only live in this page: a reload loses them. */
	get unsavedWrites(): number {
		return this.#sum((waiting) => !waiting.durable);
	}

	#sum(include: (waiting: { durable: boolean }) => boolean): number {
		let total = 0;
		for (const waiting of this.#waiting.values()) {
			if (include(waiting)) total += waiting.count;
		}
		return total;
	}

	/**
	 * A write queue reports how many ops it holds and whether the device keeps
	 * them across a reload (`durable`). 0 forgets the queue.
	 */
	reportWaiting(queue: object, count: number, durable: boolean): void {
		if (count > 0) this.#waiting.set(queue, { count, durable });
		else this.#waiting.delete(queue);
	}

	/** For tests only, through `resetCompat`. */
	clearWaiting(): void {
		this.#waiting.clear();
	}
}

export const compat = new Compat();

/**
 * Looks at the headers of one API answer. An answer without the header, or with
 * one that is not a whole number, is not a sign of a new version: proxy and
 * maintenance pages look like that during a deploy, and blocking writes for
 * them would punish the user for a short outage. Only a clear other number counts.
 */
export function checkApiVersion(headers: Pick<Headers, 'get'>): void {
	const sent = headers.get(API_VERSION_HEADER)?.trim();
	if (!sent || !/^\d+$/.test(sent)) return;
	if (Number(sent) !== EXPECTED_API_VERSION) compat.incompatible = true;
}

/** For tests only: a page cannot become compatible again without a reload. */
export function resetCompat(): void {
	compat.incompatible = false;
	compat.clearWaiting();
}
