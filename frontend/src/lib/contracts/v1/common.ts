import { Schema } from 'effect';
import { API_ERROR_CODES } from './codes';

export const ApiErrorCode = Schema.Literal(...API_ERROR_CODES);
export const ErrorResponse = Schema.Struct({
	error: Schema.Struct({ code: ApiErrorCode, message: Schema.String })
});

export const EmptyJson = Schema.Record({ key: Schema.String, value: Schema.Never });
export const Room = Schema.Struct({ slug: Schema.String, name: Schema.String });
export const RoomResponse = Schema.Struct({ room: Room });
export const ShareLink = Schema.Struct({ token: Schema.String });
export const Invitation = Schema.Struct({
	id: Schema.Int.pipe(Schema.positive()),
	status: Schema.Literal('active', 'revoked', 'expired'),
	created_at: Schema.String,
	expires_at: Schema.String,
	revoked_at: Schema.NullOr(Schema.String)
});
export const IssuedInvitation = Schema.Struct({ invitation: Invitation, token: Schema.String });

// Response UIDs are canonical. Request UIDs also accept compact, braced and URN forms.
export const Uid = Schema.String.pipe(
	Schema.pattern(/^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}(?![\s\S])/)
);
export const RequestUid = Schema.String.pipe(
	Schema.pattern(/^(?:urn:uuid:)?(?:\{[\da-f-]+\}|[\da-f-]+)(?![\s\S])/i),
	Schema.filter((value) => /^[\da-f]{32}$/i.test(value.replace(/^urn:uuid:|[{}-]/gi, '')), {
		message: () => 'Expected a UUID'
	})
);
export const Seq = Schema.NonNegativeInt;
export const Day = Schema.String.pipe(
	Schema.pattern(/^[0-9]{4}-[0-9]{2}-[0-9]{2}(?![\s\S])/),
	Schema.filter(
		(value) => {
			const date = new Date(`${value}T00:00:00Z`);
			return (
				!value.startsWith('0000') &&
				Number.isFinite(date.getTime()) &&
				date.toISOString().slice(0, 10) === value
			);
		},
		{ message: () => 'Expected a calendar day' }
	)
);
export const ClockTime = Schema.String.pipe(
	Schema.pattern(/^(?:[01][0-9]|2[0-3]):[0-5][0-9](?![\s\S])/)
);
export const ZoneName = Schema.String.pipe(Schema.minLength(1), Schema.maxLength(64));

export const Password = Schema.String.pipe(
	Schema.filter((value) => Array.from(value).length <= 1024, {
		message: () => 'Expected at most 1024 characters'
	})
);
export const PasswordBody = Schema.Struct({ password: Password });
export const CreateRoomBody = Schema.Struct({ name: Schema.String, password: Password });
