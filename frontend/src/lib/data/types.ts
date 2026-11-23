import { API_ERROR_CODES } from '#lib/contracts/v1/codes.ts';
import type * as Common from '#lib/contracts/v1/common.ts';
import type * as Feeds from '#lib/contracts/v1/feed.ts';
import type * as Ops from '#lib/contracts/v1/ops.ts';

export { API_ERROR_CODES, REJECTION_CODES } from '#lib/contracts/v1/codes.ts';

// Wire types come from the shared /api/v1 schemas, with no runtime decoding here.
export type Room = typeof Common.Room.Type;
export type ApiErrorCode = typeof Common.ApiErrorCode.Type;
export type ShareLink = typeof Common.ShareLink.Type;
export type Invitation = typeof Common.Invitation.Type;
export type IssuedInvitation = typeof Common.IssuedInvitation.Type;

export type HideDoneMode = typeof Feeds.HideDoneMode.Type;
export type HideDone = typeof Feeds.HideDone.Type;
export type TagMode = typeof Feeds.TagMode.Type;
export type TagSettings = typeof Feeds.TagSettings.Type;
export type List = typeof Feeds.List.Type;
export type Item = typeof Feeds.Item.Type;
export type Deletion = typeof Feeds.Deletion.Type;
export type Feed = typeof Feeds.Feed.Type;

export type RoomRenameOp = typeof Ops.RoomRenameOp.Type;
export type ListCreateOp = typeof Ops.ListCreateOp.Type;
export type ListRenameOp = typeof Ops.ListRenameOp.Type;
export type ListDeleteOp = typeof Ops.ListDeleteOp.Type;
export type ListTagAddOp = typeof Ops.ListTagAddOp.Type;
export type ListTagRemoveOp = typeof Ops.ListTagRemoveOp.Type;
export type ListTagSettingsOp = typeof Ops.ListTagSettingsOp.Type;
export type ListTagColorOp = typeof Ops.ListTagColorOp.Type;
export type ListTagRenameOp = typeof Ops.ListTagRenameOp.Type;
export type ListVisibilityOp = typeof Ops.ListVisibilityOp.Type;
export type ItemAddOp = typeof Ops.ItemAddOp.Type;
export type ItemSetDoneOp = typeof Ops.ItemSetDoneOp.Type;
export type ItemQuantityDeltaOp = typeof Ops.ItemQuantityDeltaOp.Type;
export type ItemEditOp = typeof Ops.ItemEditOp.Type;
export type ItemToggleTagOp = typeof Ops.ItemToggleTagOp.Type;
export type ItemDeleteOp = typeof Ops.ItemDeleteOp.Type;
export type ItemRestoreOp = typeof Ops.ItemRestoreOp.Type;
export type Op = typeof Ops.Op.Type;
export type SentOp = typeof Ops.SentOp.Type;
export type ListCreateResult = typeof Ops.ListCreateResult.Type;
export type ItemAddResult = typeof Ops.ItemAddResult.Type;
export type ItemRestoreResult = typeof Ops.ItemRestoreResult.Type;
export type RejectionCode = typeof Ops.RejectionCode.Type;
export type OpApplied = typeof Ops.OpApplied.Type;
export type OpRejected = typeof Ops.OpRejected.Type;
export type OpResponse = typeof Ops.OpResponse.Type;

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
