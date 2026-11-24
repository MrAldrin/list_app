import { Data, Effect } from 'effect';
import type { OpResponse, OpRejected, SentOp } from '#lib/contracts/v1/ops.ts';
import { trimItemName } from '#lib/data/overlay.ts';
import { apiError } from './api';

export type Operation = typeof SentOp.Type;
export type Answer = typeof OpResponse.Type;
export type Result = Extract<Answer, { status: 'applied' }>['result'];
export type Scope = { roomId: number; sharedList?: { id: number; uid: string } };
export class Refusal extends Data.TaggedError('Refusal')<
	Pick<typeof OpRejected.Type, 'code' | 'message' | 'item_uid'>
> {}
export function uuid(value: string) {
	const hex = value.replace(/^urn:uuid:|[{}-]/gi, '').toLowerCase();
	return [
		hex.slice(0, 8),
		hex.slice(8, 12),
		hex.slice(12, 16),
		hex.slice(16, 20),
		hex.slice(20)
	].join('-');
}
export function textField(raw: string, what: 'Name' | 'Description', trim = true) {
	const value = trim ? trimItemName(raw) : raw;
	const limit = what === 'Name' ? 100 : 1000;
	if (what === 'Name' && !value)
		return Effect.fail(new Refusal({ code: 'invalid_name', message: 'Name cannot be empty' }));
	if ([...value].length > limit)
		return Effect.fail(
			new Refusal({ code: 'too_long', message: `${what} can be at most ${limit} characters` })
		);
	return Effect.succeed(value);
}
export function version(base: number | undefined, current: number, matches: boolean) {
	return base !== undefined && base < current && !matches
		? Effect.fail(
				new Refusal({ code: 'changed_meanwhile', message: 'Someone else changed this meanwhile.' })
			)
		: Effect.void;
}

// Completion timestamps retain microseconds. Add times use milliseconds. Without an offset the API assumes UTC.
export function timestamp(value: string | null | undefined, digits: 3 | 6) {
	if (value == null) return null;
	try {
		const local = value.replace(' ', 'T');
		if (local.includes('[') || /:60(?:[.,Z+-]|$)/.test(local)) throw new RangeError();
		const instant = /[Tt].*(Z|[+-]\d\d(?::?\d\d(?::?\d\d(?:[.,]\d+)?)?)?)$/i.test(local)
			? Temporal.Instant.from(local)
			: Temporal.PlainDateTime.from(local).toZonedDateTime('UTC').toInstant();
		return instant.toString({ fractionalSecondDigits: digits });
	} catch {
		throw apiError(422, 'invalid_request');
	}
}
