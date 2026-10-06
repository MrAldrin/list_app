import { describe, expect, it } from 'vitest';
import { adminRoomHref } from './admin-links';

describe('admin links', () => {
	it('opens a room with ?admin=true at the root', () => {
		expect(adminRoomHref('home-ab12cd')).toBe('/room/home-ab12cd?admin=true');
	});
});
