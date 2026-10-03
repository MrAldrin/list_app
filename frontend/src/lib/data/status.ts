// The connection indicator: what to tell the user about the live stream and
// the writes that wait for the server. Pure, so Vitest can test it.

import type { LiveState } from './events';

export interface ConnectionInput {
	/** The live-updates stream. */
	live: LiveState;
	/** Writes not answered yet. */
	queued: number;
	/** A write got no answer and is being tried again. */
	retrying: boolean;
}

export interface ConnectionStatus {
	kind: 'offline' | 'saving';
	text: string;
}

/**
 * Null when all is well. A stream that is down wins over waiting writes: the
 * writes are sent once the server is back. Short waits are normal; the
 * indicator shows a status only after `CONNECTION_STATUS_DELAY`. Texts are
 * short, so they fit between the header buttons on a phone.
 */
export function connectionStatus({
	live,
	queued,
	retrying
}: ConnectionInput): ConnectionStatus | null {
	if (live === 'reconnecting') return { kind: 'offline', text: 'Reconnecting…' };
	if (live === 'connecting') return { kind: 'offline', text: 'Connecting…' };
	if (retrying || queued > 0) return { kind: 'saving', text: 'Saving…' };
	return null;
}

/** Milliseconds a status must last before it shows, so quick saves do not flicker. */
export const CONNECTION_STATUS_DELAY = 800;
