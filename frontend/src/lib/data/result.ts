// The answer of every data layer action: a result, or a message to show.
// Actions never throw for server answers or network errors.

import {
	ApiError,
	NetworkError,
	REJECTION_CODES,
	isApiErrorCode,
	isAppErrorCode,
	type ApiErrorCode,
	type AppErrorCode,
	type RejectionCode
} from './types';

/** Every code an action can fail with: the API's, a refused op's, or the app's. */
export type ActionCode = ApiErrorCode | RejectionCode | AppErrorCode;

/** True for every code an action can fail with (a stored code may be from an older build). */
export function isActionCode(code: unknown): code is ActionCode {
	return (
		isApiErrorCode(code) ||
		isAppErrorCode(code) ||
		(REJECTION_CODES as readonly unknown[]).includes(code)
	);
}

export interface Failure {
	ok: false;
	code: ActionCode;
	message: string;
}

export type ActionResult<R = Record<string, never>> = { ok: true; result: R } | Failure;

/** The text for the codes that have no server message. Other codes use `GENERIC`. */
const FALLBACK_TEXT: Partial<Record<ActionCode, string>> = {
	network: 'No connection to the server.',
	unknown: 'The change could not be saved.'
};
const GENERIC = 'Something went wrong.';

/** The text to show for a code: the server's message when it sent one, else the app's text. */
export function failureText(code: ActionCode, serverMessage = ''): string {
	return serverMessage !== '' ? serverMessage : (FALLBACK_TEXT[code] ?? GENERIC);
}

/** The failure for what a request threw. Every failed action and every failed op builds it here. */
export function failed(error: unknown): Failure {
	if (error instanceof ApiError) {
		return { ok: false, code: error.code, message: failureText(error.code, error.message) };
	}
	if (error instanceof NetworkError) {
		return { ok: false, code: 'network', message: failureText('network') };
	}
	return { ok: false, code: 'unknown', message: failureText('unknown') };
}

/** Runs one request: its result, or the failure for what it threw. */
export async function attempt<R>(request: () => Promise<R>): Promise<ActionResult<R>> {
	try {
		return { ok: true, result: await request() };
	} catch (error) {
		return failed(error);
	}
}
