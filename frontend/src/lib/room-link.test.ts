import { describe, expect, it } from 'vitest';
import { roomSlugFromInput } from './room-link';

describe('roomSlugFromInput', () => {
	it.each([
		['home-ab12cd', 'home-ab12cd'],
		['  home-ab12cd  ', 'home-ab12cd'],
		['https://listr.example/room/home-ab12cd', 'home-ab12cd'],
		['https://listr.example/room/home-ab12cd/', 'home-ab12cd'],
		['https://listr.example/app/room/home-ab12cd', 'home-ab12cd'],
		['http://192.168.1.5:8080/room/home-ab12cd?admin=true#top', 'home-ab12cd'],
		['listr.example/room/home-ab12cd', 'home-ab12cd'],
		['//listr.example/room/home-ab12cd', 'home-ab12cd'],
		['/room/home-ab12cd', 'home-ab12cd']
	])('reads %j as %j', (input, slug) => {
		expect(roomSlugFromInput(input)).toBe(slug);
	});

	it.each(['', '   ', 'https://listr.example', 'https://listr.example/', '/', '?x=1'])(
		'finds no slug in %j',
		(input) => {
			expect(roomSlugFromInput(input)).toBeNull();
		}
	);
});
