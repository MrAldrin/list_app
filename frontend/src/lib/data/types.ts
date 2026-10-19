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
	/** Empty in a share link's feed: the slug is room navigation. */
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
	/** Optional day as `YYYY-MM-DD`; null for no date. */
	date: string | null;
	/** Keep their order. */
	tags: string[];
	/** How often the item was added: adds, restores and unchecks. At least 1. */
	add_count: number;
	/** When it was last added (UTC ISO time); null for items from before counting. */
	added_at: string | null;
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
	/**
	 * Null in a share link's feed, unless this browser has access to the list's
	 * room: then the room, for "back to room" and "Reset share link".
	 */
	room: Room | null;
	lists: List[];
	items: Item[];
	deletions: Deletion[];
}

// Operations: one type per op in docs/api.md. `op_id` is added by the write queue.

export interface RoomRenameOp {
	type: 'room.rename';
	name: string;
}
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
	/** The row's `changed_seq` the page showed when the user acted. */
	base_seq?: number;
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
	/** Absent keeps the date; null clears it. */
	date?: string | null;
	base_seq: number;
}
export interface ItemToggleTagOp {
	type: 'item.toggle_tag';
	list_uid: string;
	item_uid: string;
	tag: string;
	/** The wanted state: on (`true`) or off (`false`). Safe to send twice. */
	active?: boolean;
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
	date?: string | null;
	/** Kept from the deleted item; absent counts as 1 with no time. */
	add_count?: number;
	added_at?: string | null;
}

export type Op =
	| RoomRenameOp
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

export const REJECTION_CODES = [
	'invalid_name',
	'duplicate_name',
	'duplicate_active',
	'undo_name_taken',
	'changed_meanwhile',
	'list_unavailable',
	'item_not_found',
	'too_long',
	'too_many'
] as const;
export type RejectionCode = (typeof REJECTION_CODES)[number];

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
	/** With `duplicate_active`: the uid of the item that is already on the list. */
	item_uid?: string;
}
export type OpResponse = OpApplied | OpRejected;

/** The codes the API sends in `{"error": {"code"}}` (docs/api.md, src/api/errors.py). */
export const API_ERROR_CODES = [
	'invalid_request',
	'invalid_password',
	'too_many_attempts',
	'not_authenticated',
	'admin_required',
	'share_unavailable',
	'list_unavailable',
	'wrong_password',
	'forbidden_origin',
	'not_found',
	'room_unavailable',
	'invitation_unavailable',
	'op_id_reused',
	'internal_error',
	'unavailable'
] as const;
export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

/** Codes the app makes itself, for failures the API does not name. */
export const APP_ERROR_CODES = [
	'network',
	'unknown',
	'incompatible_version',
	'read_only',
	'signed_out',
	'session_changed',
	'session_refresh_failed',
	'session_transition_unavailable',
	'logout_pending',
	'logout_marker_unacknowledged',
	'server_logout_pending',
	'local_clear_unconfirmed',
	'undo_unavailable',
	'retry_pending',
	'room_deleted'
] as const;
export type AppErrorCode = (typeof APP_ERROR_CODES)[number];

export function isAppErrorCode(code: unknown): code is AppErrorCode {
	return (APP_ERROR_CODES as readonly unknown[]).includes(code);
}

export function isApiErrorCode(code: unknown): code is ApiErrorCode {
	return (API_ERROR_CODES as readonly unknown[]).includes(code);
}

/** An HTTP error answer from the API (`{"error": {"code", "message"}}`). */
export class ApiError extends Error {
	readonly status: number;
	/** Some codes are made by the app, not sent by the API (see `AppErrorCode`). */
	readonly code: ApiErrorCode | AppErrorCode;

	constructor(status: number, code: ApiErrorCode | AppErrorCode, message: string) {
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

/** A list's share token (`…/share-link`); room members only. */
export interface ShareLink {
	token: string;
}

/** A creation invitation in the admin list. Times are UTC ISO strings. */
export interface Invitation {
	id: number;
	status: 'active' | 'revoked' | 'expired';
	created_at: string;
	expires_at: string;
	revoked_at: string | null;
}

/** A new invitation and its token: the only time the token is sent. */
export interface IssuedInvitation {
	invitation: Invitation;
	token: string;
}
