import { afterEach, expect, it, vi } from 'vitest';
import { apiError, runApi } from '#lib/server/api.ts';
import { POST } from './+server';

vi.mock('#lib/server/api.ts', async (original) => ({
	...(await original<typeof import('#lib/server/api.ts')>()),
	runApi: vi.fn()
}));

vi.mock('#lib/server/room-access.ts', () => ({
	signInToRoom: vi.fn()
}));

afterEach(() => {
	vi.unstubAllEnvs();
	vi.restoreAllMocks();
});

it('does not keep sign-in slots after unexpected failures', async () => {
	vi.stubEnv('MODE', 'typescript-server');
	const log = vi.spyOn(console, 'error').mockImplementation(() => {});
	const request = () =>
		POST({
			request: new Request('http://localhost/api/v1/rooms/home/session', {
				method: 'POST',
				body: JSON.stringify({ password: 'test-only' })
			}),
			params: { slug: 'home' },
			route: { id: '/api/v1/rooms/[slug]/session' }
		} as Parameters<typeof POST>[0]);
	vi.mocked(runApi).mockRejectedValue(new Error('Synthetic non-SQL failure'));
	for (let i = 0; i < 11; i++) expect((await request()).status).toBe(500);
	expect(log).toHaveBeenCalledTimes(11);
	vi.mocked(runApi).mockRejectedValue(apiError(401, 'invalid_password'));
	for (let i = 0; i < 10; i++) expect((await request()).status).toBe(401);
	expect((await request()).status).toBe(429);
});
