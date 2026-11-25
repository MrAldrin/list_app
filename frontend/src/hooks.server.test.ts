import { afterEach, expect, it, vi } from 'vitest';
import { handle } from './hooks.server';

vi.mock('$app/env', () => ({ building: false }));
vi.mock('#lib/server/browser-response.ts', () => ({ browserResponse: vi.fn() }));
afterEach(() => vi.unstubAllEnvs());

it('keeps Allow, not the replaced body headers, on an API method error', async () => {
	vi.stubEnv('MODE', 'typescript-server');
	const url = new URL('http://localhost/api/v1/rooms/home');
	const response = await handle({
		event: {
			url,
			request: new Request(url),
			route: { id: '/api/v1/rooms/[slug]' }
		} as Parameters<typeof handle>[0]['event'],
		resolve: async () =>
			new Response('Method Not Allowed', {
				status: 405,
				headers: { Allow: 'DELETE', 'Content-Length': '18', 'Content-Type': 'text/plain' }
			})
	});
	expect(response.status).toBe(405);
	expect(response.headers.get('Allow')).toBe('DELETE');
	expect(response.headers.get('Content-Type')).toMatch(/^application\/json/);
	const data = await response.arrayBuffer();
	expect(Number(response.headers.get('Content-Length'))).toBe(data.byteLength);
});
