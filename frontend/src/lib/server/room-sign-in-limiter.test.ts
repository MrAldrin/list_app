import { describe, expect, it } from 'vitest';
import { RoomSignInLimiter } from './room-sign-in-limiter';

describe('room sign-in slots', () => {
	it('takes a slot immediately and releases only that reservation', () => {
		const limiter = new RoomSignInLimiter(() => 0);
		const attempts = Array.from({ length: 10 }, () => limiter.reserve('room'));
		expect(limiter.reserve('room')).toEqual({ retryAfter: 60 });
		const attempt = attempts[0];
		if (!('release' in attempt)) throw new Error('Expected an available slot');
		attempt.release();
		expect(limiter.reserve('room')).toHaveProperty('release');
		attempt.release();
		expect(limiter.reserve('room')).toEqual({ retryAfter: 60 });
	});

	it('uses the longer wait when both room and global limits are full', () => {
		let now = 0;
		const limiter = new RoomSignInLimiter(() => now);
		for (let i = 0; i < 20; i++) limiter.reserve(`unrelated-${i}`);
		now = 5_250;
		for (let i = 0; i < 10; i++) limiter.reserve('room');
		now = 59_001;
		expect(limiter.reserve('another')).toEqual({ retryAfter: 1 });
		expect(limiter.reserve('room')).toEqual({ retryAfter: 7 });
		now = 60_000;
		expect(limiter.reserve('another')).toHaveProperty('release');
		expect(limiter.reserve('room')).toEqual({ retryAfter: 6 });
		now = 65_250;
		expect(limiter.reserve('room')).toHaveProperty('release');
	});
});
