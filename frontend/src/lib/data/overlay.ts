// The optimistic overlay: pending local ops projected on top of server state.
//
// Server state stays exactly as the changes feed sent it. Views read
// "server state + pending ops", so a change shows at once and settles when the
// server answers. Every op type the app can queue is projected, so the user sees
// it at once, also offline (docs/offline-viewing.md, "What works offline").

import { sortTags } from './order';
import { NEW_ROW_SEQ } from './rebase';
import type { Item, List, Room, SentOp } from './types';

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

/**
 * Ops whose projection counts twice if the server data already has them: a
 * delta adds, and a toggle without `active` flips. Set ops (with `active`, or
 * with the wanted value) project the same result however often they are applied.
 */
function countsTwice(op: SentOp): boolean {
	if (op.type === 'item.quantity_delta') return true;
	return op.type === 'item.toggle_tag' && op.active === undefined;
}

const PROJECTED = new Set<SentOp['type']>([
	'room.rename',
	'list.rename',
	'list.delete',
	'list.tag_add',
	'list.tag_remove',
	'list.visibility',
	'item.add',
	'item.set_done',
	'item.quantity_delta',
	'item.edit',
	'item.toggle_tag',
	'item.delete',
	'item.restore'
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

/**
 * A row an answered op changed: its new `changed_seq`, shown until the feed
 * reaches `appliedSeq`. Later ops then take this seq as their base (see rebase.ts).
 */
export interface AnsweredSeq {
	/** `list:<uid>` or `item:<uid>`. */
	row: string;
	changed_seq: number;
	appliedSeq: number;
}

/** Item names are stored trimmed and lowercase (docs/api.md). */
export function itemName(name: string): string {
	return name.trim().toLowerCase();
}

/**
 * Server data with the pending ops applied in order, then the answered row seqs.
 * Ops on missing rows do nothing.
 */
export function project(
	server: RoomData,
	pending: readonly PendingOp[],
	answered: readonly AnsweredSeq[] = []
): RoomData {
	if (pending.length === 0 && answered.length === 0) return server;
	const lists = new Map(server.lists);
	const items = new Map(server.items);

	for (const { op, at, uncertain } of pending) {
		if (uncertain && countsTwice(op)) continue;
		switch (op.type) {
			case 'item.set_done':
			case 'item.quantity_delta':
			case 'item.edit':
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
			case 'item.add':
				projectAdd(lists, items, op.list_uid, op.name, op.uid);
				break;
			case 'item.restore':
				projectRestore(lists, items, op);
				break;
			case 'list.tag_add':
			case 'list.tag_remove':
			case 'list.visibility':
			case 'list.rename': {
				const list = lists.get(op.list_uid);
				if (list) lists.set(list.uid, applyListOp(list, op));
				break;
			}
			case 'list.delete': {
				if (!lists.delete(op.list_uid)) break;
				for (const item of [...items.values()]) {
					if (item.list_uid === op.list_uid) items.delete(item.uid);
				}
				break;
			}
		}
	}
	for (const { row, changed_seq } of answered) {
		const uid = row.slice(row.indexOf(':') + 1);
		if (row.startsWith('list:')) {
			const list = lists.get(uid);
			if (list) lists.set(uid, { ...list, changed_seq });
		} else {
			const item = items.get(uid);
			if (item) items.set(uid, { ...item, changed_seq });
		}
	}
	return { lists, items };
}

/** The room name with pending renames applied. */
export function projectRoom(room: Room | null, pending: readonly PendingOp[]): Room | null {
	let name: string | null = null;
	for (const { op } of pending) {
		if (op.type === 'room.rename') name = op.name.trim();
	}
	return room && name !== null ? { ...room, name } : room;
}

/**
 * Add-or-restore, as the server does it: an active item with the name means no
 * change; a checked one is unchecked; otherwise a new row with the client uid.
 */
function projectAdd(
	lists: Map<string, List>,
	items: Map<string, Item>,
	listUid: string,
	rawName: string,
	uid: string | undefined
): void {
	const name = itemName(rawName);
	const same = [...items.values()].filter(
		(item) => item.list_uid === listUid && item.name === name
	);
	if (same.some((item) => !item.done)) return;
	const checked = same[0];
	if (checked) {
		items.set(checked.uid, { ...checked, done: false, completed_at: null });
		return;
	}
	if (uid === undefined || !lists.has(listUid) || items.has(uid)) return;
	items.set(uid, newRow(uid, listUid, name, { done: false, completed_at: null }));
}

/** Undo of a delete: a new row with the kept data, unless the name is taken. */
function projectRestore(
	lists: Map<string, List>,
	items: Map<string, Item>,
	op: Extract<SentOp, { type: 'item.restore' }>
): void {
	const name = itemName(op.name);
	if (op.uid === undefined || !lists.has(op.list_uid) || items.has(op.uid)) return;
	if ([...items.values()].some((item) => item.list_uid === op.list_uid && item.name === name))
		return;
	items.set(op.uid, {
		...newRow(op.uid, op.list_uid, name, {
			done: op.done,
			completed_at: op.done ? (op.completed_at ?? null) : null
		}),
		tags: op.tags,
		description: op.description.trim(),
		quantity: op.quantity
	});
}

/** An item this device created: its `changed_seq` is the placeholder until answered. */
function newRow(
	uid: string,
	listUid: string,
	name: string,
	state: Pick<Item, 'done' | 'completed_at'>
): Item {
	return {
		uid,
		list_uid: listUid,
		name,
		done: state.done,
		completed_at: state.completed_at,
		quantity: 1,
		description: '',
		tags: [],
		changed_seq: NEW_ROW_SEQ
	};
}

function applyItemOp(item: Item, op: SentOp, at: string): Item {
	switch (op.type) {
		case 'item.set_done':
			if (!op.done) return { ...item, done: false, completed_at: null };
			// Checking an already checked item keeps its time.
			return item.done ? item : { ...item, done: true, completed_at: at };
		case 'item.quantity_delta':
			return { ...item, quantity: Math.max(1, item.quantity + op.delta) };
		case 'item.edit':
			return {
				...item,
				name: itemName(op.name),
				description: op.description.trim(),
				quantity:
					op.quantity === undefined || op.quantity === null
						? item.quantity
						: Math.max(1, op.quantity)
			};
		case 'item.toggle_tag': {
			const on = op.active ?? !item.tags.includes(op.tag);
			if (!on) return { ...item, tags: item.tags.filter((tag) => tag !== op.tag) };
			return item.tags.includes(op.tag) ? item : { ...item, tags: [...item.tags, op.tag] };
		}
		default:
			return item;
	}
}

function applyListOp(list: List, op: SentOp): List {
	switch (op.type) {
		case 'list.rename':
			return { ...list, name: op.name.trim() };
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
