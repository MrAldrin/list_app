import { json, type RequestEvent } from '@sveltejs/kit';
import { Cause, Data, Exit, Option, Schema, type Effect, type ManagedRuntime } from 'effect';
import { ErrorResponse } from '#lib/contracts/v1/common.ts';
import { API_VERSION_HEADER, EXPECTED_API_VERSION } from '#lib/contracts/v1/version.ts';
import type { runtime as serverRuntime } from './runtime';

type ApiCode = typeof ErrorResponse.Type.error.code;

const messages: Record<ApiCode, string> = {
	invalid_request: 'This request is not valid.',
	invalid_password: 'Wrong room or password.',
	too_many_attempts: 'Too many attempts. Try again in a minute.',
	not_authenticated: 'Sign in to this room.',
	admin_required: 'Admin sign-in required',
	share_unavailable: 'This list was deleted or this share link was reset.',
	list_unavailable: 'The list is no longer available.',
	wrong_password: 'Incorrect password',
	forbidden_origin: 'This request must come from this site.',
	not_found: 'Not found.',
	room_unavailable: 'Room changed or no longer exists; refresh and try again',
	invitation_unavailable: 'This invitation is invalid or no longer active.',
	op_id_reused: 'This op_id was already used for another request.',
	revision_conflict: 'These settings changed in another tab. Refresh and review them.',
	not_enrolled: 'Turn on reminders on this device first.',
	internal_error: 'Something went wrong on the server.',
	unavailable: 'The server is busy. Please try again.'
};

export class ApiError extends Data.TaggedError('ApiError')<{
	readonly status: number;
	readonly code: ApiCode;
	readonly message: string;
	readonly headers?: HeadersInit;
}> {}

export function apiError(
	status: number,
	code: ApiCode,
	message = messages[code],
	headers?: HeadersInit
) {
	return new ApiError({ status, code, message, headers });
}

const encodeError = Schema.encodeSync(ErrorResponse);

export function apiErrorResponse({ status, code, message, headers }: ApiError): Response {
	return json(encodeError({ error: { code, message } }), { status, headers });
}

export function withApiHeaders(response: Response): Response {
	const headers = new Headers(response.headers);
	headers.set('Cache-Control', 'no-store');
	headers.set(API_VERSION_HEADER, String(EXPECTED_API_VERSION));
	headers.set('X-Content-Type-Options', 'nosniff');
	headers.set('X-Frame-Options', 'DENY');
	headers.set('Content-Security-Policy', "frame-ancestors 'none'");
	return new Response(response.body, {
		status: response.status,
		statusText: response.statusText,
		headers
	});
}

const writeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function isWriteMethod(method: string): boolean {
	return writeMethods.has(method);
}

export function hasSameOrigin({ request, url }: Pick<RequestEvent, 'request' | 'url'>): boolean {
	const site = request.headers.get('Sec-Fetch-Site');
	return request.headers.get('Origin') === url.origin && (site === null || site === 'same-origin');
}

export function apiWriteError(event: RequestEvent): ApiError | undefined {
	const { request } = event;
	if (!hasSameOrigin(event)) return apiError(403, 'forbidden_origin');
	const headers = request.headers;
	const hasBody =
		headers.has('Transfer-Encoding') ||
		(request.body !== null && headers.get('Content-Length') !== '0');
	const isJson =
		headers.get('Content-Type')?.split(';', 1)[0].trim().toLowerCase() === 'application/json';
	if ((request.method !== 'DELETE' || hasBody) && !isJson) {
		return apiError(415, 'invalid_request', 'Send a JSON body.');
	}
}

const MAX_BODY_BYTES = 64 * 1024;

async function readJson(request: Request): Promise<unknown> {
	const reader = request.body?.getReader();
	const decoder = new TextDecoder('utf-8', { fatal: true });
	let bytes = 0;
	let text = '';
	try {
		if (reader) {
			while (true) {
				const chunk = await reader.read();
				if (chunk.done) break;
				bytes += chunk.value.byteLength;
				if (bytes > MAX_BODY_BYTES) {
					void reader.cancel().catch(() => undefined);
					throw apiError(413, 'invalid_request', 'The request body is too large.');
				}
				text += decoder.decode(chunk.value, { stream: true });
			}
		}
		return JSON.parse(text + decoder.decode()) as unknown;
	} catch (error) {
		if (error instanceof ApiError) throw error;
		throw apiError(400, 'invalid_request', 'The body is not valid JSON.');
	} finally {
		reader?.releaseLock();
	}
}

export async function readApiBody<A, I>(request: Request, schema: Schema.Schema<A, I>): Promise<A> {
	const data = await readJson(request);
	if (typeof data !== 'object' || data === null || Array.isArray(data)) {
		throw apiError(422, 'invalid_request', 'The body must be a JSON object.');
	}
	const parsed = Schema.decodeUnknownEither(schema, { onExcessProperty: 'error' })(data);
	if (parsed._tag === 'Left') throw apiError(422, 'invalid_request');
	return parsed.right;
}

export function apiSuccess<A, I>(
	contract: { status: number; response: Schema.Schema<A, I> },
	value: A
): Response {
	const encoded = Schema.encodeSync(contract.response)(value);
	return contract.status === 204
		? new Response(null, { status: 204 })
		: json(encoded, { status: contract.status });
}

export function apiHandler<Event extends RequestEvent>(
	handler: (event: Event) => Promise<Response> | Response
): (event: Event) => Promise<Response> {
	return async (event) => {
		if (import.meta.env.MODE !== 'typescript-server') return new Response(null, { status: 404 });
		try {
			return await handler(event);
		} catch (error) {
			if (error instanceof ApiError) return apiErrorResponse(error);
			// A defect can contain user input or SQL bindings. Do not log it here.
			console.error('Unexpected API error', event.request.method, event.route.id);
			return apiErrorResponse(apiError(500, 'internal_error'));
		}
	};
}

type SqlFailure = { readonly _tag: 'SqlError' };
type ApiEffect<A> = Effect.Effect<
	A,
	ApiError | SqlFailure,
	ManagedRuntime.ManagedRuntime.Context<typeof serverRuntime>
>;

function isSqlFailure(error: unknown): error is SqlFailure {
	return (
		typeof error === 'object' && error !== null && '_tag' in error && error._tag === 'SqlError'
	);
}

export async function runApi<A>(
	{ signal }: Pick<Request, 'signal'>,
	action: ApiEffect<A>
): Promise<A> {
	const { runtime } = await import('./runtime');
	const result = await runtime.runPromiseExit(action, { signal });
	if (Exit.isSuccess(result)) return result.value;
	const failure = Option.getOrUndefined(Cause.failureOption(result.cause));
	// Effect SQL also reports transaction finalization errors as defects.
	if (isSqlFailure(failure) || [...Cause.defects(result.cause)].some(isSqlFailure)) {
		throw apiError(503, 'unavailable');
	}
	if (failure instanceof ApiError) throw failure;
	throw new Error('API effect failed');
}
