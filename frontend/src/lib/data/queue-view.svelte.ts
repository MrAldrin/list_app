// The reactive copy of one room's queue state, for components (Svelte 5 runes).
// The write queue reports every change; the room handle copies it here.

import type { HeldOp, QueueSnapshot, UnreadableOp } from './queue-entries';

export class QueueView {
	/** Every stored op that waits, including held and unreadable ones. */
	waiting = $state(0);
	/** Older than 30 days: sent only after the user chooses (R10). */
	held = $state.raw<HeldOp[]>([]);
	/** Waiting for an explicit send choice after sign-out. */
	signoutHeld = $state.raw<HeldOp[]>([]);
	/** Kept but not sent: a newer app wrote it, or it fails validation (R13). */
	unreadable = $state.raw<UnreadableOp[]>([]);
	/** False when the ops live in memory only (R11). */
	durable = $state(true);

	apply(snapshot: QueueSnapshot): void {
		this.waiting = snapshot.waiting;
		this.held = snapshot.held;
		this.signoutHeld = snapshot.signoutHeld;
		this.unreadable = snapshot.unreadable;
		this.durable = snapshot.durable;
	}
}
