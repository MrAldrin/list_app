// The data shapes of the JSON API. The contract is docs/api.md.

export interface Room {
	slug: string;
	name: string;
}

export type HideDoneMode = 'off' | 'all' | 'age' | 'recent';

export interface HideDone {
	mode: HideDoneMode;
	age_days: number;
	recent_count: number;
}

export interface List {
	uid: string;
	slug: string;
	name: string;
	/** Sorted ignoring case. */
	tags: string[];
	hide_done: HideDone;
	changed_seq: number;
}

export interface Item {
	uid: string;
	list_uid: string;
	/** Stored in lowercase. */
	name: string;
	done: boolean;
	/** UTC ISO time, or null when not done or not known. */
	completed_at: string | null;
	quantity: number;
	description: string;
	/** Keep their order. */
	tags: string[];
	changed_seq: number;
}

export interface Deletion {
	kind: 'list' | 'item';
	uid: string;
}

/** One answer of `GET …/changes?since=N`. */
export interface Feed {
	seq: number;
	full: boolean;
	room: Room;
	lists: List[];
	items: Item[];
	deletions: Deletion[];
}

// Operations: one type per op in docs/api.md. `op_id` is added by the write queue.

export interface ListCreateOp {
	type: 'list.create';
	name: string;
	uid?: string;
}
export interface ListRenameOp {
	type: 'list.rename';
	list_uid: string;
	name: string;
	base_seq: number;
}
export interface ListDeleteOp {
	type: 'list.delete';
	list_uid: string;
}
export interface ListTagAddOp {
	type: 'list.tag_add';
	list_uid: string;
	tag: string;
}
export interface ListTagRemoveOp {
	type: 'list.tag_remove';
	list_uid: string;
	tag: string;
}
export interface ListVisibilityOp {
	type: 'list.visibility';
	list_uid: string;
	mode?: HideDoneMode;
	age_days?: number;
	recent_count?: number;
}
export interface ItemAddOp {
	type: 'item.add';
	list_uid: string;
	name: string;
	uid?: string;
}
export interface ItemSetDoneOp {
	type: 'item.set_done';
	list_uid: string;
	item_uid: string;
	done: boolean;
}
export interface ItemQuantityDeltaOp {
	type: 'item.quantity_delta';
	list_uid: string;
	item_uid: string;
	delta: number;
}
export interface ItemEditOp {
	type: 'item.edit';
	list_uid: string;
	item_uid: string;
	name: string;
	description: string;
	quantity?: number | null;
	base_seq: number;
}
export interface ItemToggleTagOp {
	type: 'item.toggle_tag';
	list_uid: string;
	item_uid: string;
	tag: string;
}
export interface ItemDeleteOp {
	type: 'item.delete';
	list_uid: string;
	item_uid: string;
}
export interface ItemRestoreOp {
	type: 'item.restore';
	list_uid: string;
	uid?: string;
	name: string;
	done: boolean;
	tags: string[];
	description: string;
	quantity: number;
	completed_at: string | null;
}

export type Op =
	| ListCreateOp
	| ListRenameOp
	| ListDeleteOp
	| ListTagAddOp
	| ListTagRemoveOp
	| ListVisibilityOp
	| ItemAddOp
	| ItemSetDoneOp
	| ItemQuantityDeltaOp
	| ItemEditOp
	| ItemToggleTagOp
	| ItemDeleteOp
	| ItemRestoreOp;

/** An op as sent: with its client-made, retry-safe `op_id`. */
export type SentOp = Op & { op_id: string };

export interface ListCreateResult {
	list_uid: string;
	slug: string;
	created: boolean;
}
export interface ItemAddResult {
	item_uid: string;
	outcome: 'added' | 'restored';
}
export interface ItemRestoreResult {
	item_uid: string;
}

export type RejectionCode =
	| 'invalid_name'
	| 'duplicate_name'
	| 'duplicate_active'
	| 'undo_name_taken'
	| 'list_unavailable'
	| 'item_not_found';

export interface OpApplied {
	op_id: string;
	status: 'applied';
	result: Record<string, unknown>;
	seq: number;
}
export interface OpRejected {
	op_id: string;
	status: 'rejected';
	code: RejectionCode;
	message: string;
	seq: number;
}
export type OpResponse = OpApplied | OpRejected;

export type ErrorCode =
	| 'invalid_request'
	| 'invalid_password'
	| 'not_authenticated'
	| 'forbidden_origin'
	| 'not_found'
	| 'op_id_reused'
	| 'internal_error'
	| 'unavailable';

/** An HTTP error answer from the API (`{"error": {"code", "message"}}`). */
export class ApiError extends Error {
	readonly status: number;
	readonly code: ErrorCode | string;

	constructor(status: number, code: ErrorCode | string, message: string) {
		super(message);
		this.name = 'ApiError';
		this.status = status;
		this.code = code;
	}
}

/** The request never got an HTTP answer: offline, server down, DNS, CORS. */
export class NetworkError extends Error {
	constructor(message = 'No connection to the server.') {
		super(message);
		this.name = 'NetworkError';
	}
}
