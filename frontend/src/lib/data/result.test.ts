import { describe, expect, it } from 'vitest';
import { failed, failureText, isActionCode } from './result';
import { ApiError, NetworkError } from './types';

describe('failed', () => {
	it('keeps the server code and message of an API error', () => {
		expect(failed(new ApiError(401, 'not_authenticated', 'Sign in to this room.'))).toEqual({
			ok: false,
			code: 'not_authenticated',
			message: 'Sign in to this room.'
		});
	});

	it('names a missing connection as network with the app text', () => {
		expect(failed(new NetworkError())).toEqual({
			ok: false,
			code: 'network',
			message: 'No connection to the server.'
		});
	});

	it('gives any other thrown value the unknown code and text', () => {
		const expected = { ok: false, code: 'unknown', message: 'The change could not be saved.' };
		expect(failed(new TypeError('Cannot read properties'))).toEqual(expected);
		expect(failed('boom')).toEqual(expected);
	});
});

describe('failureText', () => {
	it('uses the server message when there is one', () => {
		expect(failureText('wrong_password', 'Incorrect password')).toBe('Incorrect password');
	});

	it('uses the app text for a code without a server message', () => {
		expect(failureText('network')).toBe('No connection to the server.');
		expect(failureText('unknown', '')).toBe('The change could not be saved.');
	});

	it('uses the generic text for other codes without a message', () => {
		expect(failureText('session_changed')).toBe('Something went wrong.');
	});
});

describe('isActionCode', () => {
	it('accepts API, refused-op and app codes', () => {
		expect(isActionCode('room_unavailable')).toBe(true);
		expect(isActionCode('too_long')).toBe(true);
		expect(isActionCode('signed_out')).toBe(true);
	});

	it('rejects codes this build does not know', () => {
		expect(isActionCode('made_up_code')).toBe(false);
		expect(isActionCode(undefined)).toBe(false);
	});
});
