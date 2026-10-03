// The optimistic overlay: pending local ops projected on top of server state.
//
// Server state stays exactly as the changes feed sent it. Views read
// "server state + pending ops", so a change shows at once and settles when the
// server answers. Only simple ops are projected; the others (add, edit, rename,
// create, restore, list delete) wait for the server.

import { sortTags } from './order';
import type { Item, List, SentOp } from './types';

export interface PendingOp {
	op: SentOp;
	/** When the user did it (ISO time), used as the projected `completed_at`. */
	at: string;
	/** The room `seq` after the server applied it; null while not answered. */
	appliedSeq: number | null;
	/**
	 * Sent without an answer (it is being retried): the server may have applied
	 * it already, so a feed may include it. Ops that are not safe to apply twice
	 * are then not projected (see `project`).
	 */
	uncertain?: boolean;
}

/** Ops whose projection would count twice if the server data already has them. */
const NOT_IDEMPOTENT = new Set<SentOp['type']>(['item.quantity_delta', 'item.toggle_tag']);

const PROJECTED = new Set<SentOp['type']>([
	'item.set_done',
	'item.quantity_delta',
	'item.toggle_tag',
	'item.delete',
	'list.tag_add',
	'list.tag_remove',
	'list.visibility'
]);

/** The current time as an ISO string, for a projected `completed_at`. */
export function nowIso(): string {
	return new Date().toISOString();
}

export function isProjected(op: SentOp): boolean {
	return PROJECTED.has(op.type);
}

export interface RoomData {
	lists: ReadonlyMap<string, List>;
	items: ReadonlyMap<string, Item>;
}

/** Server data with the pending ops applied in order. Ops on missing rows do nothing. */
export function project(server: RoomData, pending: readonly PendingOp[]): RoomData {
	if (pending.length === 0) return server;
	const lists = new Map(server.lists);
	const items = new Map(server.items);

	for (const { op, at, uncertain } of pending) {
		if (uncertain && NOT_IDEMPOTENT.has(op.type)) continue;
		switch (op.type) {
			case 'item.set_done':
			case 'item.quantity_delta':
			case 'item.toggle_tag': {
				const item = items.get(op.item_uid);
				if (!item || item.list_uid !== op.list_uid) break;
				items.set(item.uid, applyItemOp(item, op, at));
				break;
			}
			case 'item.delete': {
				const item = items.get(op.item_uid);
				if (item && item.list_uid === op.list_uid) items.delete(item.uid);
				break;
			}
			case 'list.tag_add':
			case 'list.tag_remove':
			case 'list.visibility': {
				const list = lists.get(op.list_uid);
				if (list) lists.set(list.uid, applyListOp(list, op));
				break;
			}
		}
	}
	return { lists, items };
}

function applyItemOp(item: Item, op: SentOp, at: string): Item {
	switch (op.type) {
		case 'item.set_done':
			if (!op.done) return { ...item, done: false, completed_at: null };
			// Checking an already checked item keeps its time.
			return item.done ? item : { ...item, done: true, completed_at: at };
		case 'item.quantity_delta':
			return { ...item, quantity: Math.max(1, item.quantity + op.delta) };
		case 'item.toggle_tag':
			return {
				...item,
				tags: item.tags.includes(op.tag)
					? item.tags.filter((tag) => tag !== op.tag)
					: [...item.tags, op.tag]
			};
		default:
			return item;
	}
}

function applyListOp(list: List, op: SentOp): List {
	switch (op.type) {
		case 'list.tag_add': {
			const tag = op.tag.trim();
			if (!tag || list.tags.includes(tag)) return list;
			return { ...list, tags: sortTags([...list.tags, tag]) };
		}
		case 'list.tag_remove':
			return { ...list, tags: list.tags.filter((tag) => tag !== op.tag) };
		case 'list.visibility': {
			const hideDone = { ...list.hide_done };
			if (op.mode !== undefined) hideDone.mode = op.mode;
			if (op.age_days !== undefined) hideDone.age_days = op.age_days;
			if (op.recent_count !== undefined) hideDone.recent_count = op.recent_count;
			return { ...list, hide_done: hideDone };
		}
		default:
			return list;
	}
}
