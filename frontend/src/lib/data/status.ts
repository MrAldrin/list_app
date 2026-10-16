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

/**
 * Milliseconds a saved view may wait for its first server answer before the
 * offline notice shows. Online, the answer usually comes first, so the
 * notice does not flash and push the page down. A failed read shows it at once.
 */
export const SAVED_VIEW_NOTICE_DELAY = 1500;

/** "18:05" when `savedAt` is today, else "12 Oct, 18:05". Null if unusable. */
export function savedTimeLabel(
	savedAt: string | null,
	now: Date = new Date(),
	locale?: string
): string | null {
	if (!savedAt) return null;
	const date = new Date(savedAt);
	if (Number.isNaN(date.valueOf())) return null;
	const time = date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' });
	if (date.toDateString() === now.toDateString()) return time;
	const day = date.toLocaleDateString(locale, { day: 'numeric', month: 'short' });
	return `${day}, ${time}`;
}

/** The offline notice (docs/offline-viewing.md, "The offline notice"). */
export function offlineNoticeText(): string {
	return "Offline — changes are saved on this phone and sent when you're back online.";
}

/** "1 change waiting to be sent." or "N changes waiting to be sent."; null for none. */
export function waitingChangesText(queued: number): string | null {
	if (queued <= 0) return null;
	return `${queued} ${queued === 1 ? 'change' : 'changes'} waiting to be sent.`;
}
