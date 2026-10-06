import { describe, expect, it } from 'vitest';
import { adminRoomHref } from './admin-links';

describe('admin links', () => {
	it('opens a room with ?admin=true under the app base path', () => {
		expect(adminRoomHref('home-ab12cd')).toBe('/app/room/home-ab12cd?admin=true');
	});
});
