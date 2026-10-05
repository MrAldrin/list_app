import { describe, expect, it } from 'vitest';
import { adminRoomHref, openedFromAdmin } from './admin-links';

describe('admin links', () => {
	it('opens a room with ?admin=true under the app base path', () => {
		expect(adminRoomHref('home-ab12cd')).toBe('/app/room/home-ab12cd?admin=true');
	});

	it.each([
		['https://listr.example/app/room/home?admin=true', true],
		['https://listr.example/app/room/home', false],
		['https://listr.example/app/room/home?admin=1', false],
		['https://listr.example/app/room/home?admin=TRUE', false]
	])('reads %j as opened from admin: %j', (url, expected) => {
		expect(openedFromAdmin(new URL(url))).toBe(expected);
	});
});
