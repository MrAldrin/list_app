// One stored write-queue entry: what the device keeps for an op until the
// server answers it (plans/offline-editing.md, R10 and R13). Pure functions only;
// storage lives in queue-storage.ts and the queue in write-queue.ts.

import { isRecord } from './snapshot-validate';
import type { Op, SentOp } from './types';

/** The entry format this build writes and reads. A newer number is kept but not sent. */
export const QUEUE_FORMAT = 1;

/** Pending ops older than this (by `at`) are held: sent only when the user says so. */
export const HOLD_MS = 30 * 24 * 60 * 60 * 1000;

/** `pending`: waits to be sent. `approved`: the user chose to send it after a hold. */
export type EntryState = 'pending' | 'approved';

/**
 * What the device stores per op. Fields are `unknown` because a stored entry may
 * come from another app version or a damaged record; `classifyEntry` checks them.
 */
export interface StoredEntry {
	opId: string;
	/** The op JSON, with `op_id`. */
	op: unknown;
	/** ISO time when the user acted. */
	at: unknown;
	format: unknown;
	state: unknown;
}

export function newStoredEntry(op: SentOp, at: string): StoredEntry {
	return { opId: op.op_id, op, at, format: QUEUE_FORMAT, state: 'pending' satisfies EntryState };
}

const str = (value: unknown) => typeof value === 'string';
const num = (value: unknown) => typeof value === 'number' && Number.isFinite(value);
const bool = (value: unknown) => typeof value === 'boolean';
const strs = (value: unknown) => Array.isArray(value) && value.every(str);
const optional =
	(check: (value: unknown) => boolean) =>
	(value: unknown): boolean =>
		value === undefined || check(value);
const nullable =
	(check: (value: unknown) => boolean) =>
	(value: unknown): boolean =>
		value === null || check(value);

type Checks = Record<string, (value: unknown) => boolean>;

/** The fields each op type needs (docs/api.md, "Writing: operations"). */
const FIELDS: Record<Op['type'], Checks> = {
	'room.rename': { name: str },
	'list.create': { name: str, uid: optional(str) },
	'list.rename': { list_uid: str, name: str, base_seq: num },
	'list.delete': { list_uid: str },
	'list.tag_add': { list_uid: str, tag: str },
	'list.tag_remove': { list_uid: str, tag: str },
	'list.visibility': {
		list_uid: str,
		mode: optional(str),
		age_days: optional(num),
		recent_count: optional(num)
	},
	'item.add': { list_uid: str, name: str, uid: optional(str) },
	'item.set_done': { list_uid: str, item_uid: str, done: bool },
	'item.quantity_delta': { list_uid: str, item_uid: str, delta: num },
	'item.edit': {
		list_uid: str,
		item_uid: str,
		name: str,
		description: str,
		quantity: optional(nullable(num)),
		base_seq: num
	},
	'item.toggle_tag': { list_uid: str, item_uid: str, tag: str },
	'item.delete': { list_uid: str, item_uid: str },
	'item.restore': {
		list_uid: str,
		uid: optional(str),
		name: str,
		done: bool,
		tags: strs,
		description: str,
		quantity: num,
		completed_at: nullable(str)
	}
};

/** True when `value` is an op this build knows how to send. */
export function isSentOp(value: unknown): value is SentOp {
	if (!isRecord(value) || !str(value.op_id) || value.op_id === '') return false;
	const type = value.type;
	if (typeof type !== 'string' || !Object.hasOwn(FIELDS, type)) return false;
	return Object.entries(FIELDS[type as Op['type']]).every(([name, check]) => check(value[name]));
}

export type UnreadableReason = 'newer_format' | 'invalid';

export type Verdict =
	| { kind: 'ready'; op: SentOp }
	| { kind: 'held'; op: SentOp; at: string | null }
	| { kind: 'unreadable'; reason: UnreadableReason };

/**
 * Decides what the queue does with one entry. `now` is epoch milliseconds.
 * - Unknown format: unreadable (a newer app wrote it), kept, not sent.
 * - Op fails validation, or unknown state: unreadable, kept, not sent.
 * - Pending and older than 30 days, or with no usable `at`: held.
 */
export function classifyEntry(entry: StoredEntry, now: number): Verdict {
	if (entry.format !== QUEUE_FORMAT) {
		const newer = typeof entry.format === 'number' && entry.format > QUEUE_FORMAT;
		return { kind: 'unreadable', reason: newer ? 'newer_format' : 'invalid' };
	}
	if (!isSentOp(entry.op) || entry.op.op_id !== entry.opId) {
		return { kind: 'unreadable', reason: 'invalid' };
	}
	if (entry.state !== 'pending' && entry.state !== 'approved') {
		return { kind: 'unreadable', reason: 'invalid' };
	}
	const at = str(entry.at) ? (entry.at as string) : null;
	if (entry.state === 'approved') return { kind: 'ready', op: entry.op };
	const time = at === null ? NaN : Date.parse(at);
	// `!(… <= …)` also holds an unparsable time.
	if (!(now - time <= HOLD_MS)) return { kind: 'held', op: entry.op, at };
	return { kind: 'ready', op: entry.op };
}

export interface HeldOp {
	opId: string;
	at: string | null;
	op: SentOp;
}

export interface UnreadableOp {
	opId: string;
	at: string | null;
	format: unknown;
	reason: UnreadableReason;
}

/** What the room shows: counts and lists, computed from the stored entries. */
export interface QueueSnapshot {
	/** Every stored entry, including held and unreadable ones. */
	waiting: number;
	held: HeldOp[];
	unreadable: UnreadableOp[];
	/** False when entries live only in memory (no IndexedDB, or it failed). */
	durable: boolean;
}

export function summarizeEntries(
	entries: readonly StoredEntry[],
	now: number,
	durable: boolean
): QueueSnapshot {
	const held: HeldOp[] = [];
	const unreadable: UnreadableOp[] = [];
	for (const entry of entries) {
		const verdict = classifyEntry(entry, now);
		const at = str(entry.at) ? (entry.at as string) : null;
		if (verdict.kind === 'held') held.push({ opId: entry.opId, at, op: verdict.op });
		else if (verdict.kind === 'unreadable') {
			unreadable.push({ opId: entry.opId, at, format: entry.format, reason: verdict.reason });
		}
	}
	return { waiting: entries.length, held, unreadable, durable };
}
