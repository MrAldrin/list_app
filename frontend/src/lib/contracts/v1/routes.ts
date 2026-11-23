import { Schema } from 'effect';
import {
	CreateRoomBody,
	EmptyJson,
	Invitation,
	IssuedInvitation,
	Password,
	PasswordBody,
	RequestUid,
	Room,
	RoomResponse,
	ShareLink
} from './common';
import { EventFrame, RoomFeed, ShareFeed } from './feed';
import { OpResponse, SentOp, SentShareOp } from './ops';
import {
	DevicePatchBody,
	DeviceResponse,
	DeviceWriteResponse,
	EnrollBody,
	EnrollmentPatchBody,
	EnrollmentResponse,
	EnrollmentWriteResponse,
	PolicyBody,
	PolicyResponse,
	Preview,
	PreviewBody,
	RoomPolicyBody
} from './reminders';

const RoomPath = Schema.Struct({ slug: Schema.String });
const TokenPath = Schema.Struct({ token: Schema.String });
const ShareLinkPath = Schema.Struct({ ...RoomPath.fields, list_uid: RequestUid });
// Policy paths also accept an old numeric target ID.
const PolicyPath = Schema.Struct({ ...RoomPath.fields, target_id: Schema.String });
const SqliteIntegerText = Schema.String.pipe(
	Schema.pattern(/^[0-9]+(?![\s\S])/),
	Schema.filter((text) => BigInt(text) <= 9_223_372_036_854_775_807n)
);
const SinceQuery = Schema.Struct({ since: SqliteIntegerText });
const InvitationIdPath = Schema.Struct({
	invitation_id: SqliteIntegerText.pipe(Schema.filter((text) => BigInt(text) > 0n))
});
const ChangePasswordBody = Schema.Struct({ current_password: Password, new_password: Password });
const ResetPasswordBody = Schema.Struct({ new_password: Password });

// Paths are relative to /api/v1. Errors use ErrorResponse from common.ts.
// Params and query describe URL values, not JSON. For SSE, response describes
// one parsed frame, not the stream. Cookie and header rules stay in docs/api.md.
export const API_V1 = {
	'GET /last-room': {
		status: 200,
		response: Schema.Struct({ slug: Schema.NullOr(Schema.String) })
	},
	'POST /rooms/{slug}/session': {
		params: RoomPath,
		body: PasswordBody,
		status: 200,
		response: RoomResponse
	},
	'GET /rooms/{slug}/session': { params: RoomPath, status: 200, response: RoomResponse },
	'DELETE /rooms/{slug}/session': { params: RoomPath, status: 204, response: Schema.Undefined },
	'POST /rooms/{slug}/password': {
		params: RoomPath,
		body: ChangePasswordBody,
		status: 200,
		response: RoomResponse
	},
	'DELETE /rooms/{slug}': {
		params: RoomPath,
		body: PasswordBody,
		status: 204,
		response: Schema.Undefined
	},
	'GET /rooms/{slug}/changes': {
		params: RoomPath,
		query: SinceQuery,
		status: 200,
		response: RoomFeed
	},
	'POST /rooms/{slug}/ops': { params: RoomPath, body: SentOp, status: 200, response: OpResponse },
	'GET /rooms/{slug}/events': { params: RoomPath, status: 200, response: EventFrame },
	'GET /rooms/{slug}/lists/{list_uid}/share-link': {
		params: ShareLinkPath,
		status: 200,
		response: ShareLink
	},
	'POST /rooms/{slug}/lists/{list_uid}/share-link': {
		params: ShareLinkPath,
		body: EmptyJson,
		status: 200,
		response: ShareLink
	},
	'GET /share/{token}/changes': {
		params: TokenPath,
		query: SinceQuery,
		status: 200,
		response: ShareFeed
	},
	'POST /share/{token}/ops': {
		params: TokenPath,
		body: SentShareOp,
		status: 200,
		response: OpResponse
	},
	'GET /share/{token}/events': { params: TokenPath, status: 200, response: EventFrame },
	'POST /admin/session': { body: PasswordBody, status: 200, response: EmptyJson },
	'GET /admin/session': { status: 200, response: EmptyJson },
	'DELETE /admin/session': { status: 204, response: Schema.Undefined },
	'GET /admin/rooms': {
		status: 200,
		response: Schema.Struct({ rooms: Schema.mutable(Schema.Array(Room)) })
	},
	'POST /admin/rooms': { body: CreateRoomBody, status: 200, response: RoomResponse },
	'POST /admin/rooms/{slug}/password': {
		params: RoomPath,
		body: ResetPasswordBody,
		status: 200,
		response: EmptyJson
	},
	'DELETE /admin/rooms/{slug}': { params: RoomPath, status: 204, response: Schema.Undefined },
	'GET /admin/invitations': {
		status: 200,
		response: Schema.Struct({ invitations: Schema.mutable(Schema.Array(Invitation)) })
	},
	'POST /admin/invitations': { body: EmptyJson, status: 200, response: IssuedInvitation },
	'POST /admin/invitations/{invitation_id}/revoke': {
		params: InvitationIdPath,
		body: EmptyJson,
		status: 200,
		response: EmptyJson
	},
	'GET /invitations/{token}': { params: TokenPath, status: 200, response: EmptyJson },
	'POST /invitations/{token}/rooms': {
		params: TokenPath,
		body: CreateRoomBody,
		status: 200,
		response: RoomResponse
	},
	'POST /rooms/{slug}/reminders/enrollment': {
		params: RoomPath,
		body: EnrollBody,
		status: 200,
		response: EnrollmentWriteResponse
	},
	'GET /rooms/{slug}/reminders/preferences': {
		params: RoomPath,
		status: 200,
		response: EnrollmentResponse
	},
	'PATCH /rooms/{slug}/reminders/preferences': {
		params: RoomPath,
		body: EnrollmentPatchBody,
		status: 200,
		response: EnrollmentWriteResponse
	},
	'GET /rooms/{slug}/reminders/preferences/device': {
		params: RoomPath,
		status: 200,
		response: DeviceResponse
	},
	'PATCH /rooms/{slug}/reminders/preferences/device': {
		params: RoomPath,
		body: DevicePatchBody,
		status: 200,
		response: DeviceWriteResponse
	},
	'GET /rooms/{slug}/reminders/policy': { params: RoomPath, status: 200, response: PolicyResponse },
	'PUT /rooms/{slug}/reminders/policy': {
		params: RoomPath,
		body: RoomPolicyBody,
		status: 200,
		response: PolicyResponse
	},
	'GET /rooms/{slug}/reminders/lists/{target_id}/policy': {
		params: PolicyPath,
		status: 200,
		response: PolicyResponse
	},
	'PUT /rooms/{slug}/reminders/lists/{target_id}/policy': {
		params: PolicyPath,
		body: PolicyBody,
		status: 200,
		response: PolicyResponse
	},
	'GET /rooms/{slug}/reminders/items/{target_id}/policy': {
		params: PolicyPath,
		status: 200,
		response: PolicyResponse
	},
	'PUT /rooms/{slug}/reminders/items/{target_id}/policy': {
		params: PolicyPath,
		body: PolicyBody,
		status: 200,
		response: PolicyResponse
	},
	'POST /rooms/{slug}/reminders/preview': {
		params: RoomPath,
		body: PreviewBody,
		status: 200,
		response: Preview
	}
} as const;
