import { describe, expect, it } from 'vitest';
import { readReveal, revealHref } from './reveal';

describe('revealHref and readReveal', () => {
	it('round-trips the item and makes each tap a new key', () => {
		const first = revealHref('/room/home/list/groceries', 'item-1', 100);
		expect(first).toBe('/room/home/list/groceries?item=item-1&at=100');
		const reveal = readReveal(new URL(`http://x${first}`).searchParams);
		expect(reveal).toEqual({ uid: 'item-1', key: 'item-1@100' });
		const again = readReveal(new URL(`http://x${revealHref('', 'item-1', 200)}`).searchParams);
		expect(again?.key).not.toBe(reveal?.key);
	});

	it('ignores a URL without an item', () => {
		expect(readReveal(new URLSearchParams('at=5'))).toBeNull();
		expect(readReveal(new URLSearchParams(''))).toBeNull();
	});

	it('encodes the item in the link', () => {
		expect(revealHref('', 'a b&c', 1)).toBe('?item=a%20b%26c&at=1');
	});
});
