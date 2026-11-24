import type { RequestEvent } from '@sveltejs/kit';
import { createHash, createHmac, randomBytes, scrypt, timingSafeEqual } from 'node:crypto';
import { Effect, Redacted } from 'effect';
import { apiError, runApi } from './api';
import { RoomSignInLimiter } from './room-sign-in-limiter';
import { ServerConfig } from './runtime';

const SESSION_SECONDS = 30 * 60;
const TOKEN_DOMAIN = 'listapp-admin-session\0';
const TOKEN_PATTERN = /^(v2\.([0-9]+)\.[a-f0-9]{32})\.([a-f0-9]{64})(?![\s\S])/;
type CookieEvent = Pick<RequestEvent, 'cookies' | 'url'>;

// One bucket for all admin attempts, separate from the room limiter.
const limiter = new RoomSignInLimiter();

function cookieName(url: URL): string {
	return url.protocol === 'https:' ? '__Host-listapp-admin' : 'listapp-admin';
}

function cookieOptions(url: URL) {
	return { path: '/', secure: url.protocol === 'https:', httpOnly: true, sameSite: 'lax' } as const;
}

function adminCookie({ cookies, url }: CookieEvent): string | undefined {
	return cookies.get(cookieName(url), { decode: (raw) => raw });
}

export function hasAdminCookie(event: CookieEvent): boolean {
	return adminCookie(event) !== undefined;
}

export function setAdminCookie({ cookies, url }: CookieEvent, token: string): void {
	cookies.set(cookieName(url), token, { ...cookieOptions(url), maxAge: SESSION_SECONDS });
}

export function clearAdminCookie({ cookies, url }: CookieEvent): void {
	cookies.delete(cookieName(url), cookieOptions(url));
}

// APP_PASSWORD is fixed for the life of the runtime. Cache the slow key
// derivation, including while it is in flight. Keep the existing v2 wire format.
let signingKey: Promise<Buffer> | undefined;
function keyFor(password: Redacted.Redacted) {
	signingKey ??= new Promise<Buffer>((resolve, reject) => {
		scrypt(
			Redacted.value(password),
			'listr-admin-cookie-v2',
			32,
			{ N: 2 ** 16, r: 8, p: 1, maxmem: 128 * 1024 * 1024 },
			(error, key) => {
				if (error) {
					signingKey = undefined;
					reject(error);
				} else resolve(key);
			}
		);
	});
	return signingKey;
}

function sign(payload: string, key: Buffer): Buffer {
	return createHmac('sha256', key).update(TOKEN_DOMAIN).update(payload).digest();
}

function passwordDigest(password: string): Buffer {
	return createHash('sha256').update(password).digest();
}

export function signInAsAdmin(password: string) {
	return Effect.gen(function* () {
		const attempt = limiter.reserve('admin');
		if ('retryAfter' in attempt) {
			return yield* apiError(429, 'too_many_attempts', undefined, {
				'Retry-After': String(attempt.retryAfter)
			});
		}
		const { appPassword } = yield* ServerConfig;
		if (!timingSafeEqual(passwordDigest(password), passwordDigest(Redacted.value(appPassword)))) {
			return yield* apiError(401, 'invalid_password', 'Wrong password');
		}
		const key = yield* Effect.promise(() => keyFor(appPassword));
		const expiry = Math.floor(Date.now() / 1000) + SESSION_SECONDS;
		const payload = `v2.${expiry}.${randomBytes(16).toString('hex')}`;
		const token = `${payload}.${sign(payload, key).toString('hex')}`;
		attempt.release();
		return token;
	});
}

function validAdminToken(token: string | undefined) {
	return Effect.gen(function* () {
		if (!token || token.length > 256) return false;
		const parts = TOKEN_PATTERN.exec(token);
		if (!parts || Number(parts[2]) <= Date.now() / 1000) return false;
		const { appPassword } = yield* ServerConfig;
		const key = yield* Effect.promise(() => keyFor(appPassword));
		return (
			timingSafeEqual(Buffer.from(parts[3], 'hex'), sign(parts[1], key)) &&
			Number(parts[2]) > Date.now() / 1000
		);
	});
}

export async function requireAdmin(event: RequestEvent): Promise<void> {
	const token = adminCookie(event);
	if (!token || !(await runApi(event.request, validAdminToken(token)))) {
		throw apiError(401, 'admin_required');
	}
}
