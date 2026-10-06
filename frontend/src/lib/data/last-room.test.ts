import { describe, expect, it, vi } from 'vitest';
import { lastRoom } from './index';
import type { SnapshotStore } from './snapshot-store';
import { ApiError, NetworkError } from './types';

function savedRoom(value: string | null) {
	return { lastRoom: vi.fn(async () => ({ ok: true as const, value })) } as Pick<
		SnapshotStore,
		'lastRoom'
	>;
}

describe('lastRoom routing fallback', () => {
	it('uses the saved routing hint when the server is offline', async () => {
		const client = { lastRoom: vi.fn(async () => Promise.reject(new NetworkError())) };
		const snapshots = savedRoom('home-ab12cd');

		expect(await lastRoom(client, snapshots)).toBe('home-ab12cd');
		expect(snapshots.lastRoom).toHaveBeenCalledOnce();
	});

	it('falls back on temporary gateway and unavailable answers', async () => {
		for (const error of [
			new ApiError(503, 'unavailable', 'Busy'),
			new ApiError(502, 'internal_error', 'Gateway error')
		]) {
			const client = { lastRoom: vi.fn(async () => Promise.reject(error)) };
			expect(await lastRoom(client, savedRoom('home-ab12cd'))).toBe('home-ab12cd');
		}
	});

	it('does not fall back on authorization or other permanent answers', async () => {
		const error = new ApiError(401, 'not_authenticated', 'Sign in.');
		const client = { lastRoom: vi.fn(async () => Promise.reject(error)) };
		const snapshots = savedRoom('home-ab12cd');

		await expect(lastRoom(client, snapshots)).rejects.toBe(error);
		expect(snapshots.lastRoom).not.toHaveBeenCalled();
	});

	it('preserves the server error if local routing storage is unavailable', async () => {
		const error = new NetworkError();
		const client = { lastRoom: vi.fn(async () => Promise.reject(error)) };
		const snapshots = {
			lastRoom: vi.fn(async () => ({ ok: false as const, reason: 'unavailable' as const }))
		} as unknown as Pick<SnapshotStore, 'lastRoom'>;

		await expect(lastRoom(client, snapshots)).rejects.toBe(error);
	});
});
