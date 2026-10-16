// Rewrites of queued ops after the server answered an earlier op
// (plans/offline-editing.md, R3 and R6). Pure functions: the write queue applies
// the result to memory and storage, and the room store to its projection.
//
// Rule for a body rewrite: only ops that were never sent are rewritten. An op
// that is in flight, or was sent and is being retried, keeps the body it was
// sent with, because its `op_id` must keep meaning that body (docs/api.md).

import type { OpResponse, SentOp } from './types';

/** `changed_seq` of a row this device created and the server has not answered for yet. */
export const NEW_ROW_SEQ = 0;

export interface Rewrite {
	opId: string;
	op: SentOp;
}

export interface RewriteInput {
	/** The op that was answered (already removed from the queue). */
	settled: SentOp;
	response: OpResponse;
	/** The ops still queued, in send order. */
	later: readonly SentOp[];
	/** True for an op that was sent (in flight or retried): its body stays. */
	sent: (opId: string) => boolean;
	/** The row's `changed_seq` the device knows, for rows the server has. */
	knownSeq: (row: string) => number | undefined;
}

/** The row an op changes: `list:<uid>` or `item:<uid>`. Null for ops on no row yet. */
export function rowOf(op: SentOp): string | null {
	switch (op.type) {
		case 'item.set_done':
		case 'item.quantity_delta':
		case 'item.edit':
		case 'item.toggle_tag':
		case 'item.delete':
			return `item:${op.item_uid}`;
		case 'list.rename':
		case 'list.delete':
		case 'list.tag_add':
		case 'list.tag_remove':
		case 'list.visibility':
			return `list:${op.list_uid}`;
		default:
			return null;
	}
}

function hasBase(op: SentOp): op is SentOp & { base_seq: number } {
	return 'base_seq' in op && typeof op.base_seq === 'number';
}

function withBase(op: SentOp, base_seq: number): SentOp {
	return { ...op, base_seq } as SentOp;
}

function withItemUid(op: SentOp, item_uid: string): SentOp {
	return { ...op, item_uid } as SentOp;
}

/**
 * The item uid the server kept for an `item.add`: the answer's `item_uid`
 * (applied, or the existing item of a `duplicate_active` rejection).
 */
function keptItemUid(response: OpResponse): string | undefined {
	const uid = response.status === 'applied' ? response.result.item_uid : response.item_uid;
	return typeof uid === 'string' ? uid : undefined;
}

/**
 * The row an applied op changed (`list:<uid>` or `item:<uid>`). An add or restore
 * changed the row the server kept.
 */
export function changedRow(settled: SentOp, response: OpResponse): string | null {
	if (
		response.status === 'applied' &&
		(settled.type === 'item.add' || settled.type === 'item.restore')
	) {
		const uid = response.result.item_uid;
		return typeof uid === 'string' ? `item:${uid}` : null;
	}
	return rowOf(settled);
}

/**
 * The later queued ops to rewrite, with their new bodies.
 *
 * - R6, uid remap: an `item.add` answered with another item uid (`restored`,
 *   or `duplicate_active`) moves the later ops on the client uid to the kept
 *   uid. An op that was based on the new row's placeholder (`NEW_ROW_SEQ`) takes
 *   the row's `changed_seq` instead, when the answer has one.
 * - R3, own ops: after an applied op with a `changed_seq`, later ops on the same
 *   row whose `base_seq` equals the row's value before this op take the new
 *   value. "Before" is the settled op's own `base_seq`, or the row's known seq.
 */
export function planRewrites(input: RewriteInput): Rewrite[] {
	const { settled, response, later, sent, knownSeq } = input;
	const rewritten = new Map<string, SentOp>();
	const latest = (op: SentOp): SentOp => rewritten.get(op.op_id) ?? op;
	const changedSeq =
		response.status === 'applied' && typeof response.result.changed_seq === 'number'
			? response.result.changed_seq
			: undefined;

	const kept = settled.type === 'item.add' ? keptItemUid(response) : undefined;
	if (
		kept !== undefined &&
		settled.type === 'item.add' &&
		settled.uid !== undefined &&
		kept !== settled.uid
	) {
		for (const op of later) {
			if (sent(op.op_id) || !('item_uid' in op) || op.item_uid !== settled.uid) continue;
			let next = withItemUid(op, kept);
			if (hasBase(next) && next.base_seq === NEW_ROW_SEQ) {
				next = withBase(next, changedSeq ?? knownSeq(`item:${kept}`) ?? NEW_ROW_SEQ);
			}
			rewritten.set(op.op_id, next);
		}
	}

	if (changedSeq !== undefined) {
		const row = changedRow(settled, response);
		if (row !== null) {
			const before = hasBase(settled) ? settled.base_seq : (knownSeq(row) ?? NEW_ROW_SEQ);
			for (const op of later) {
				const current = latest(op);
				if (sent(op.op_id) || !hasBase(current) || current.base_seq !== before) continue;
				if (rowOf(current) !== row) continue;
				rewritten.set(op.op_id, withBase(current, changedSeq));
			}
		}
	}

	return [...rewritten].map(([opId, op]) => ({ opId, op }));
}
