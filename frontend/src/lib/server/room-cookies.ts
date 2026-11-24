import type { RequestEvent } from '@sveltejs/kit';
import { createHash } from 'node:crypto';

type CookieEvent = Pick<RequestEvent, 'cookies' | 'url'>;
const ONE_YEAR = 365 * 24 * 60 * 60;

export function hashToken(token: string): string {
	return createHash('sha256').update(token).digest('hex');
}

function schemeCookie(url: URL, suffix: string): string {
	return (url.protocol === 'https:' ? '__Host-' : '') + 'listapp-' + suffix;
}

function roomCookieName(url: URL, slug: string): string {
	return schemeCookie(url, 'room-' + hashToken(slug));
}

function lastRoomCookieName(url: URL): string {
	return schemeCookie(url, 'last-room');
}

function cookieOptions(url: URL) {
	return { path: '/', secure: url.protocol === 'https:', httpOnly: true, sameSite: 'lax' } as const;
}

function readCookie({ cookies }: CookieEvent, name: string): string | undefined {
	return cookies.get(name, { decode: (raw) => raw });
}

function boundedValue(value: string | undefined): string | null {
	return value && Array.from(value).length <= 256 ? value : null;
}

export function hasRoomCookie(event: CookieEvent, slug: string): boolean {
	return readCookie(event, roomCookieName(event.url, slug)) !== undefined;
}

export function roomToken(event: CookieEvent, slug: string): string | null {
	return boundedValue(readCookie(event, roomCookieName(event.url, slug)));
}

export function lastRoom(event: CookieEvent): string | null {
	return boundedValue(readCookie(event, lastRoomCookieName(event.url)));
}

export function setRoomCookies({ cookies, url }: CookieEvent, slug: string, token: string): void {
	const options = { ...cookieOptions(url), maxAge: ONE_YEAR };
	cookies.set(roomCookieName(url, slug), token, options);
	cookies.set(lastRoomCookieName(url), slug, options);
}

export function clearRoomCookie({ cookies, url }: CookieEvent, slug: string): void {
	cookies.delete(roomCookieName(url, slug), cookieOptions(url));
}

export function clearDeletedRoomCookies(event: CookieEvent, slug: string): void {
	clearRoomCookie(event, slug);
	if (lastRoom(event) === slug) {
		event.cookies.delete(lastRoomCookieName(event.url), cookieOptions(event.url));
	}
}
