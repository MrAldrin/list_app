import { describe, expect, it } from 'vitest';
import {
	cantBeSentText,
	countsAsWaited,
	notSavedCountText,
	notSavedMessage,
	notSentYetText,
	unsentRows,
	WAITED_MS,
	willBeDiscardedText
} from './not-saved';
import type { SentOp } from './types';

const base = { op_id: 'op-1' };
const setDone: SentOp = {
	...base,
	type: 'item.set_done',
	list_uid: 'l1',
	item_uid: 'i1',
	done: true,
	base_seq: 4
};

describe('notSavedMessage', () => {
	it('says what and why for a changed row, with the name the user saw', () => {
		expect(
			notSavedMessage({ op: setDone, code: 'changed_meanwhile', message: '', name: 'milk' })
		).toBe("Tick 'milk': someone else changed it meanwhile.");
		const untick: SentOp = { ...setDone, done: false };
		expect(
			notSavedMessage({ op: untick, code: 'changed_meanwhile', message: '', name: 'milk' })
		).toBe("Untick 'milk': someone else changed it meanwhile.");
	});

	it('says an item was deleted by someone else, for edits and other item ops', () => {
		const edit: SentOp = {
			...base,
			type: 'item.edit',
			list_uid: 'l1',
			item_uid: 'i1',
			name: 'milk',
			description: '',
			base_seq: 2
		};
		expect(notSavedMessage({ op: edit, code: 'item_not_found', message: '', name: 'milk' })).toBe(
			"Edit 'milk': it was deleted by someone else."
		);
		expect(
			notSavedMessage({
				op: { ...base, type: 'item.delete', list_uid: 'l1', item_uid: 'i1' },
				code: 'item_not_found',
				message: '',
				name: null
			})
		).toBe('Delete the item: it was deleted by someone else.');
	});

	it('names the list when the list is gone', () => {
		const rename: SentOp = {
			...base,
			type: 'list.rename',
			list_uid: 'l1',
			name: 'Food',
			base_seq: 1
		};
		expect(
			notSavedMessage({ op: rename, code: 'list_unavailable', message: '', name: 'Shop' })
		).toBe("Rename list to 'Food': the list was deleted by someone else.");
		expect(
			notSavedMessage({
				op: { ...base, type: 'list.delete', list_uid: 'l1' },
				code: 'list_unavailable',
				message: '',
				name: null
			})
		).toBe('Delete the list: the list was deleted by someone else.');
	});

	it('says a name is taken, for renames and undo', () => {
		const rename: SentOp = {
			...base,
			type: 'list.rename',
			list_uid: 'l1',
			name: 'Food',
			base_seq: 1
		};
		expect(notSavedMessage({ op: rename, code: 'duplicate_name', message: '', name: 'Shop' })).toBe(
			"Rename list to 'Food': that name is taken."
		);
		const restore: SentOp = {
			...base,
			type: 'item.restore',
			list_uid: 'l1',
			uid: 'i2',
			name: 'milk',
			done: false,
			tags: [],
			description: '',
			quantity: 1,
			completed_at: null
		};
		expect(notSavedMessage({ op: restore, code: 'undo_name_taken', message: '', name: null })).toBe(
			"Undo delete of 'milk': that name is taken now."
		);
	});

	it('says why for empty and long names', () => {
		const add: SentOp = { ...base, type: 'item.add', list_uid: 'l1', name: '' };
		expect(notSavedMessage({ op: add, code: 'invalid_name', message: '', name: null })).toBe(
			"Add '': the name cannot be empty."
		);
		expect(notSavedMessage({ op: add, code: 'too_long', message: '', name: null })).toBe(
			"Add '': it is too long."
		);
	});

	it('uses the server message for a count limit, which names the limit', () => {
		const add: SentOp = { ...base, type: 'item.add', list_uid: 'l1', name: 'eggs' };
		expect(
			notSavedMessage({
				op: add,
				code: 'too_many',
				message: 'A list can have at most 1000 items',
				name: null
			})
		).toBe("Add 'eggs': A list can have at most 1000 items.");
	});

	it('uses the server message for other codes, with a full stop', () => {
		const add: SentOp = { ...base, type: 'item.add', list_uid: 'l1', name: 'eggs' };
		expect(
			notSavedMessage({
				op: add,
				code: 'duplicate_active',
				message: "'eggs' is already on the list",
				name: null
			})
		).toBe("Add 'eggs': 'eggs' is already on the list.");
		expect(notSavedMessage({ op: add, code: 'unknown', message: '  ', name: null })).toBe(
			"Add 'eggs': it could not be saved."
		);
	});

	it('describes tag, quantity and list changes', () => {
		expect(
			notSavedMessage({
				op: { ...base, type: 'item.toggle_tag', list_uid: 'l1', item_uid: 'i1', tag: 'Market' },
				code: 'item_not_found',
				message: '',
				name: 'milk'
			})
		).toBe("Change tag 'Market' on 'milk': it was deleted by someone else.");
		expect(
			notSavedMessage({
				op: { ...base, type: 'list.tag_add', list_uid: 'l1', tag: 'Home' },
				code: 'list_unavailable',
				message: '',
				name: 'Shop'
			})
		).toBe("Add tag 'Home' to list 'Shop': the list was deleted by someone else.");
	});
});

describe('countsAsWaited', () => {
	const now = 1_000_000;
	const quick = { offline: false, loaded: false, queuedAt: now, answeredAt: now + 500 };

	it('keeps a quick online answer as a toast', () => {
		expect(countsAsWaited(quick)).toBe(false);
	});

	it('counts an op made offline, loaded from storage, or answered late', () => {
		expect(countsAsWaited({ ...quick, offline: true })).toBe(true);
		expect(countsAsWaited({ ...quick, loaded: true })).toBe(true);
		expect(countsAsWaited({ ...quick, answeredAt: now + WAITED_MS })).toBe(false);
		expect(countsAsWaited({ ...quick, answeredAt: now + WAITED_MS + 1 })).toBe(true);
	});
});

describe('unsentRows', () => {
	it('lists the item and list rows with an op not answered yet', () => {
		const rows = unsentRows([
			{ op: setDone, appliedSeq: null },
			{
				op: { ...base, type: 'item.add', list_uid: 'l1', name: 'eggs', uid: 'i9' },
				appliedSeq: null
			},
			{ op: { ...base, type: 'list.tag_add', list_uid: 'l2', tag: 'Home' }, appliedSeq: null },
			{ op: { ...base, type: 'item.delete', list_uid: 'l1', item_uid: 'old' }, appliedSeq: 9 }
		]);
		expect([...rows].sort()).toEqual(['item:i1', 'item:i9', 'list:l2']);
	});
});

describe('count texts', () => {
	it('uses the singular for one change', () => {
		expect(notSavedCountText(1)).toBe('1 change was not saved');
		expect(notSavedCountText(2)).toBe('2 changes were not saved');
		expect(notSentYetText(1)).toBe(
			"1 waiting change in this room's queue on this device will be held after sign-out."
		);
		expect(notSentYetText(3)).toBe(
			"3 waiting changes in this room's queue on this device will be held after sign-out."
		);
	});
});

describe('sentences for the sheet and the banner', () => {
	it('uses the singular and the share link wording', () => {
		expect(cantBeSentText(1, false)).toBe("1 change can't be sent. Sign in again to send it.");
		expect(cantBeSentText(2, false)).toBe("2 changes can't be sent. Sign in again to send them.");
		expect(cantBeSentText(2, true)).toBe("2 changes can't be sent. This share link was reset.");
		expect(willBeDiscardedText(1)).toBe('1 waiting change on this phone will be discarded.');
		expect(willBeDiscardedText(3)).toBe('3 waiting changes on this phone will be discarded.');
	});
});
