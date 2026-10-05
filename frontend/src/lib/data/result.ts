// The answer of every data layer action: a result, or a message to show.
// Actions never throw for server answers or network errors.

import { ApiError } from './types';

export type ActionResult<R = Record<string, never>> =
	{ ok: true; result: R } | { ok: false; code: string; message: string };

export function failed(error: unknown): { ok: false; code: string; message: string } {
	if (error instanceof ApiError) return { ok: false, code: error.code, message: error.message };
	if (error instanceof Error) return { ok: false, code: 'network', message: error.message };
	return { ok: false, code: 'unknown', message: 'Something went wrong.' };
}
