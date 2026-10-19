import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	encodeRememberedRooms,
	forgetRoom,
	forgetRoomIn,
	MAX_REMEMBERED_ROOMS,
	parseRememberedRooms,
	readRememberedRooms,
	rememberRoom,
	rememberRoomIn,
	ROOMS_COOKIE,
	type RememberedRoom
} from './remembered-rooms.ts';

function room(index: number): RememberedRoom {
	return { slug: `room-${index}-ab12cd`, name: `Room ${index}` };
}

function listOf(count: number): RememberedRoom[] {
	return Array.from({ length: count }, (_, index) => room(index));
}

describe('parseRememberedRooms', () => {
	it('reads a list written as an encoded JSON array', () => {
		const raw = encodeURIComponent(JSON.stringify([room(1), room(2)]));
		expect(parseRememberedRooms(raw)).toEqual([room(1), room(2)]);
	});

	it('gives an empty list for a missing or broken value', () => {
		expect(parseRememberedRooms(null)).toEqual([]);
		expect(parseRememberedRooms('')).toEqual([]);
		expect(parseRememberedRooms('%7B%22not%22%3A1%7D')).toEqual([]);
		expect(parseRememberedRooms('not json')).toEqual([]);
		expect(parseRememberedRooms('%E0%A4%A')).toEqual([]); // Not valid encoding.
	});

	it('drops entries that are not a valid slug and name', () => {
		const raw = encodeURIComponent(
			JSON.stringify([
				room(1),
				{ slug: 'Bad Slug!', name: 'x' },
				{ slug: 'ok-ab12cd', name: '   ' },
				{ slug: 'ok-ab12cd', name: 'n'.repeat(101) },
				{ slug: 'ok-ab12cd' },
				'home-ab12cd',
				null
			])
		);
		expect(parseRememberedRooms(raw)).toEqual([room(1)]);
	});

	it('keeps at most the cap', () => {
		const raw = encodeURIComponent(JSON.stringify(listOf(14)));
		expect(parseRememberedRooms(raw)).toHaveLength(MAX_REMEMBERED_ROOMS);
	});
});

describe('rememberRoomIn and forgetRoomIn', () => {
	it('puts a newly entered room first', () => {
		expect(rememberRoomIn([room(1)], room(2))).toEqual([room(2), room(1)]);
	});

	it('moves a known room to the front and takes its new name', () => {
		const rooms = [room(1), room(2)];
		expect(rememberRoomIn(rooms, { slug: room(2).slug, name: 'Renamed' })).toEqual([
			{ slug: room(2).slug, name: 'Renamed' },
			room(1)
		]);
	});

	it('drops the oldest room when the cap is reached', () => {
		const full = listOf(MAX_REMEMBERED_ROOMS);
		const next = rememberRoomIn(full, { slug: 'new-ab12cd', name: 'New' });
		expect(next).toHaveLength(MAX_REMEMBERED_ROOMS);
		expect(next[0]).toEqual({ slug: 'new-ab12cd', name: 'New' });
		expect(next.map((item) => item.slug)).not.toContain(room(MAX_REMEMBERED_ROOMS - 1).slug);
	});

	it('removes one room and keeps the others in order', () => {
		expect(forgetRoomIn([room(1), room(2), room(3)], room(2).slug)).toEqual([room(1), room(3)]);
		expect(forgetRoomIn([room(1)], 'unknown-ab12cd')).toEqual([room(1)]);
	});
});

describe('encodeRememberedRooms', () => {
	it('round-trips through parse', () => {
		const rooms = [room(1), { slug: 'cafe-ab12cd', name: 'Café ✓ 家' }];
		expect(parseRememberedRooms(encodeRememberedRooms(rooms))).toEqual(rooms);
	});

	it('drops the oldest rooms when long names would exceed the cookie size', () => {
		const long = Array.from({ length: 10 }, (_, index) => ({
			slug: `long-${index}-ab12cd`,
			name: '家'.repeat(100)
		}));
		const encoded = encodeRememberedRooms(long);
		expect(encoded.length).toBeLessThanOrEqual(3000);
		const kept = parseRememberedRooms(encoded);
		expect(kept.length).toBeGreaterThan(0);
		expect(kept[0]).toEqual(long[0]);
	});
});

describe('the browser cookie', () => {
	const jar = { cookie: '' };
	beforeEach(() => {
		jar.cookie = '';
		vi.stubGlobal('document', jar);
		vi.stubGlobal('location', { protocol: 'https:' });
	});
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('writes a plain, Secure, one-year cookie over HTTPS and reads it back', () => {
		rememberRoom(room(1).slug, room(1).name);
		rememberRoom(room(2).slug, room(2).name);

		expect(jar.cookie).toContain('; Secure');
		expect(jar.cookie).not.toContain('HttpOnly');
		expect(jar.cookie).toContain('Max-Age=31536000');
		expect(readRememberedRooms()).toEqual([room(2), room(1)]);
	});

	it('does not add Secure over plain HTTP', () => {
		vi.stubGlobal('location', { protocol: 'http:' });
		rememberRoom(room(1).slug, room(1).name);
		expect(jar.cookie).not.toContain('Secure');
	});

	it('removes a room, and deletes the cookie when no room is left', () => {
		rememberRoom(room(1).slug, room(1).name);
		forgetRoom(room(1).slug);
		expect(jar.cookie).toContain('Max-Age=0');
		expect(jar.cookie).toMatch(new RegExp(`^${ROOMS_COOKIE}=;`));
		expect(readRememberedRooms()).toEqual([]);
	});
});
