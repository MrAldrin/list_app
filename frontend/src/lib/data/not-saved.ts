// Changes the user is told about after the server refused them, or failed them
// (plans/offline-editing.md, 6.3). Pure functions: room-store.svelte.ts keeps
// the list, the components show it.

import type { SentOp } from './types';

/** An op answered after this long (queued that long before) counts as waited. */
export const WAITED_MS = 10_000;

export interface WaitInput {
	/** Made while the page could not write (offline, or access being checked). */
	offline: boolean;
	/** Read from storage: made on an earlier visit. */
	loaded: boolean;
	/** When the op was queued (epoch milliseconds). */
	queuedAt: number;
	/** When the answer came (epoch milliseconds). */
	answeredAt: number;
}

/**
 * True when a rejection or failure of this op goes to the Not saved list
 * instead of a toast. A quick online answer keeps the toast: the user just
 * saw the change happen.
 */
export function countsAsWaited({ offline, loaded, queuedAt, answeredAt }: WaitInput): boolean {
	return offline || loaded || answeredAt - queuedAt > WAITED_MS;
}

export interface NotSavedInput {
	op: SentOp;
	/** The rejection code, or a code the app made for a failure. */
	code: string;
	/** The server's message, used when the code has no text of its own. */
	message: string;
	/** The item or list name the user saw, or null when it is not known. */
	name: string | null;
}

const ITEM = (name: string | null) => (name === null ? 'the item' : `'${name}'`);
const LIST = (name: string | null) => (name === null ? 'the list' : `list '${name}'`);

/** What the user tried to do, in plain words. */
function actionOf(op: SentOp, name: string | null): string {
	switch (op.type) {
		case 'item.set_done':
			return `${op.done ? 'Tick' : 'Untick'} ${ITEM(name)}`;
		case 'item.quantity_delta':
			return `Change quantity of ${ITEM(name)}`;
		case 'item.edit':
			return `Edit ${ITEM(name)}`;
		case 'item.toggle_tag':
			return `Change tag '${op.tag}' on ${ITEM(name)}`;
		case 'item.delete':
			return `Delete ${ITEM(name)}`;
		case 'item.add':
			return `Add '${op.name}'`;
		case 'item.restore':
			return `Undo delete of '${op.name}'`;
		case 'list.create':
			return `Create list '${op.name}'`;
		case 'list.rename':
			return `Rename list to '${op.name}'`;
		case 'list.delete':
			return `Delete ${LIST(name)}`;
		case 'list.tag_add':
			return `Add tag '${op.tag}' to ${LIST(name)}`;
		case 'list.tag_remove':
			return `Remove tag '${op.tag}' from ${LIST(name)}`;
		case 'list.visibility':
			return `Change hide-done settings of ${LIST(name)}`;
		case 'room.rename':
			return `Rename room to '${op.name}'`;
	}
}

/** Why, for the codes the app knows. Other codes use the server message. */
const REASONS: Readonly<Record<string, string>> = {
	changed_meanwhile: 'someone else changed it meanwhile.',
	item_not_found: 'it was deleted by someone else.',
	list_unavailable: 'the list was deleted by someone else.',
	duplicate_name: 'that name is taken.',
	undo_name_taken: 'that name is taken now.',
	invalid_name: 'the name cannot be empty.',
	too_long: 'it is too long.'
};

/** A server message as a sentence: trimmed, with a full stop when it has none. */
function sentence(message: string): string {
	const text = message.trim();
	if (text === '') return 'it could not be saved.';
	return /[.!?]$/.test(text) ? text : `${text}.`;
}

/** "Tick 'milk': someone else changed it meanwhile." */
export function notSavedMessage(input: NotSavedInput): string {
	const reason = Object.hasOwn(REASONS, input.code) ? REASONS[input.code] : sentence(input.message);
	return `${actionOf(input.op, input.name)}: ${reason}`;
}

/** Rows ("item:<uid>" or "list:<uid>") that have a change not answered yet. */
export function unsentRows(
	pending: readonly { op: SentOp; appliedSeq: number | null }[]
): Set<string> {
	const rows = new Set<string>();
	for (const { op, appliedSeq } of pending) {
		if (appliedSeq !== null) continue;
		switch (op.type) {
			case 'item.set_done':
			case 'item.quantity_delta':
			case 'item.edit':
			case 'item.toggle_tag':
			case 'item.delete':
				rows.add(`item:${op.item_uid}`);
				break;
			case 'item.add':
			case 'item.restore':
				if (op.uid) rows.add(`item:${op.uid}`);
				break;
			case 'list.rename':
			case 'list.delete':
			case 'list.tag_add':
			case 'list.tag_remove':
			case 'list.visibility':
				rows.add(`list:${op.list_uid}`);
				break;
			default:
				break;
		}
	}
	return rows;
}

/** "1 change is not sent yet." or "2 changes are not sent yet." (`count` > 0). */
export function notSentYetText(count: number): string {
	return count === 1 ? '1 change is not sent yet.' : `${count} changes are not sent yet.`;
}

/** The banner's count: "1 change was not saved", "2 changes were not saved". */
export function notSavedCountText(count: number): string {
	return count === 1 ? '1 change was not saved' : `${count} changes were not saved`;
}
