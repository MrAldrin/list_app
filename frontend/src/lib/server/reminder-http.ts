import type { RequestEvent } from '@sveltejs/kit';
import { DEVICE_LIFETIME_SECONDS } from './reminder-store';
import { roomToken } from './room-cookies';

function deviceCookieName(url: URL) {
	return url.protocol === 'https:' ? '__Host-listapp-device' : 'listapp-device';
}

export function reminderAccess(event: RequestEvent, slug: string) {
	const secret = event.cookies.get(deviceCookieName(event.url), { decode: (raw) => raw });
	return {
		slug,
		roomToken: roomToken(event, slug),
		deviceSecret: secret && [...secret].length <= 256 ? secret : null
	};
}

export function setDeviceCookie({ cookies, url }: RequestEvent, secret: string) {
	cookies.set(deviceCookieName(url), secret, {
		path: '/',
		httpOnly: true,
		sameSite: 'lax',
		secure: url.protocol === 'https:',
		maxAge: DEVICE_LIFETIME_SECONDS
	});
}
