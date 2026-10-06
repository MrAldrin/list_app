import { describe, expect, it } from 'vitest';
import { isNetworkOnlyNavigation } from '#lib/worker-routes.ts';

describe('isNetworkOnlyNavigation', () => {
	it.each(['/admin', '/admin/', '/admin/login', '/app', '/app/share/token', '/app/admin'])(
		'leaves %s to the network',
		(path) => expect(isNetworkOnlyNavigation(path)).toBe(true)
	);

	it.each([
		'/',
		'/room/home-abc123',
		'/room/admin',
		'/list/x',
		'/share/t',
		'/administrator',
		'/apple'
	])('serves %s from the saved shell', (path) => expect(isNetworkOnlyNavigation(path)).toBe(false));
});
