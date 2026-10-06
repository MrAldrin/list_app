import { describe, expect, it } from 'vitest';
import { manifestHref } from './manifest';

const BASE = '';

describe('manifestHref', () => {
	it('links the room manifest on the room page', () => {
		expect(manifestHref('/room/[slug]', { slug: 'home-ab12cd' }, BASE)).toBe(
			'/room-manifest/home-ab12cd.webmanifest'
		);
	});

	it('encodes the slug as one path part', () => {
		expect(manifestHref('/room/[slug]', { slug: 'room"?><& #/x' }, BASE)).toBe(
			'/room-manifest/room%22%3F%3E%3C%26%20%23%2Fx.webmanifest'
		);
	});

	it.each([
		['/', {}],
		['/room/[slug]/list/[list]', { slug: 'home-ab12cd', list: 'groceries' }],
		['/list/[slug]', { slug: 'groceries' }],
		['/share/[token]', { token: 'secret-share-token' }],
		['/admin', {}],
		['/create-room/[token]', { token: 'secret-invitation' }],
		[null, {}],
		['/room/[slug]', {}]
	])('links the default manifest on %s', (routeId, params) => {
		const href = manifestHref(routeId, params, BASE);
		expect(href).toBe('/manifest.webmanifest');
		expect(href).not.toContain('secret');
	});

	it('adds a base path when the app is served under one', () => {
		expect(manifestHref('/room/[slug]', { slug: 'home' }, '/sub')).toBe(
			'/sub/room-manifest/home.webmanifest'
		);
		expect(manifestHref('/', {}, '/sub')).toBe('/sub/manifest.webmanifest');
	});
});
