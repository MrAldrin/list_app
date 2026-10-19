// The "Rooms" list in the room menu: the rooms this browser entered, most
// recent first. It is a routing hint only. Opening a room still needs its
// password or a valid token, and the list never holds a token or a password.
//
// The page writes the cookie, not the server: the page knows the room name at
// each room entry, and sign-out and room deletion also happen in the page. The
// cookie is plain (not HttpOnly) and holds no secret.

export const ROOMS_COOKIE = 'listapp-rooms';
const COOKIE_MAX_AGE = 31536000; // One year, in seconds.
export const MAX_REMEMBERED_ROOMS = 10;
/** Browsers keep about 4 KB per cookie; stay well below that. */
const MAX_COOKIE_CHARS = 3000;
const MAX_NAME_LENGTH = 100; // The server's room name limit.
const SLUG_PATTERN = /^[a-z0-9-]{1,120}$/;

export interface RememberedRoom {
	slug: string;
	name: string;
}

function validRoom(item: unknown): item is RememberedRoom {
	if (typeof item !== 'object' || item === null) return false;
	const { slug, name } = item as Record<string, unknown>;
	return (
		typeof slug === 'string' &&
		SLUG_PATTERN.test(slug) &&
		typeof name === 'string' &&
		name.trim() !== '' &&
		name.length <= MAX_NAME_LENGTH
	);
}

/** The rooms in a cookie value. A bad or missing value gives an empty list. */
export function parseRememberedRooms(raw: string | null): RememberedRoom[] {
	if (!raw) return [];
	try {
		const data: unknown = JSON.parse(decodeURIComponent(raw));
		if (!Array.isArray(data)) return [];
		return data.filter(validRoom).slice(0, MAX_REMEMBERED_ROOMS);
	} catch {
		return [];
	}
}

/** The list with this room first (its new name, if it changed), at most the cap. */
export function rememberRoomIn(rooms: RememberedRoom[], room: RememberedRoom): RememberedRoom[] {
	const others = rooms.filter((item) => item.slug !== room.slug);
	return [{ slug: room.slug, name: room.name }, ...others].slice(0, MAX_REMEMBERED_ROOMS);
}

/** The list without this room. */
export function forgetRoomIn(rooms: RememberedRoom[], slug: string): RememberedRoom[] {
	return rooms.filter((item) => item.slug !== slug);
}

/** The cookie value for a list. Drops the oldest rooms if the value gets too long. */
export function encodeRememberedRooms(rooms: RememberedRoom[]): string {
	let kept = rooms.slice(0, MAX_REMEMBERED_ROOMS);
	let encoded = encodeURIComponent(JSON.stringify(kept));
	while (encoded.length > MAX_COOKIE_CHARS && kept.length > 1) {
		kept = kept.slice(0, -1);
		encoded = encodeURIComponent(JSON.stringify(kept));
	}
	return encoded;
}

/** The value of one cookie in a `document.cookie` string, or null. */
function cookieValue(name: string, cookies: string): string | null {
	for (const part of cookies.split(';')) {
		const [key, ...rest] = part.trim().split('=');
		if (key === name) return rest.join('=');
	}
	return null;
}

/** `Secure` only on HTTPS: plain HTTP (local tests) still gets the cookie. */
function secureSuffix(): string {
	return location.protocol === 'https:' ? '; Secure' : '';
}

function setPageCookie(name: string, value: string): void {
	document.cookie = `${name}=${value}; Path=/; Max-Age=${COOKIE_MAX_AGE}; SameSite=Lax${secureSuffix()}`;
}

function deletePageCookie(name: string): void {
	document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax${secureSuffix()}`;
}

/** The rooms this browser remembers. */
export function readRememberedRooms(): RememberedRoom[] {
	try {
		return parseRememberedRooms(cookieValue(ROOMS_COOKIE, document.cookie));
	} catch {
		return [];
	}
}

function update(change: (rooms: RememberedRoom[]) => RememberedRoom[]): void {
	try {
		const before = readRememberedRooms();
		const after = change(before);
		if (after.length === 0) {
			deletePageCookie(ROOMS_COOKIE);
		} else if (JSON.stringify(after) !== JSON.stringify(before)) {
			setPageCookie(ROOMS_COOKIE, encodeRememberedRooms(after));
		}
	} catch {
		// Cookies are blocked: the list stays empty; routing still works.
	}
}

/** Adds (or moves to the front) a room that this browser just entered. */
export function rememberRoom(slug: string, name: string): void {
	update((rooms) => rememberRoomIn(rooms, { slug, name }));
}

/** Removes a room after sign-out or when it was deleted. */
export function forgetRoom(slug: string): void {
	update((rooms) => forgetRoomIn(rooms, slug));
}
