// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import * as data from '#lib/data/index.ts';
import { makeFeed, makeList, waitFor } from '#lib/data/test-helpers.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import { click, fill, submit } from '#lib/test-support/dom.ts';
import RoomPage from '../../routes/room/[slug]/+page.svelte';
import { ReminderApi } from '#lib/reminders/api.ts';

vi.mock('$app/state', () => ({
	page: { params: { slug: 'home-ab12cd' }, url: new URL('http://localhost/room/home-ab12cd') }
}));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('#lib/data/index.ts', async (original) => ({
	...(await original<typeof data>()),
	openRoom: vi.fn(),
	closeRoom: (room: data.RoomHandle) => room.release()
}));

it('an open rename sends then signs out on 401', async () => {
	const enrollment = vi
		.spyOn(ReminderApi.prototype, 'enrollment')
		.mockResolvedValue({ enrollment: { state: 'not_enrolled', revision: null } });
	const list = makeList();
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list] }));
	vi.mocked(data.openRoom).mockReturnValue(fixture.room);
	fixture.api.sendOp.mockRejectedValue(
		new data.ApiError(401, 'not_authenticated', 'Sign in to this room.')
	);
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(RoomPage, { target });
	try {
		flushSync();
		click(target, 'Rename Groceries');
		fill(target.querySelector('dialog input')!, 'forbidden rename');
		submit(target.querySelector('dialog')!);
		await waitFor(() => expect(fixture.api.sendOp).toHaveBeenCalledTimes(1));
		expect(fixture.api.sendOp.mock.calls[0]).toEqual([
			fixture.room.slug,
			{
				op_id: expect.any(String),
				type: 'list.rename',
				list_uid: list.uid,
				name: 'forbidden rename',
				base_seq: list.changed_seq
			}
		]);
		await waitFor(() => expect(fixture.room.store.status).toBe('auth_required'));
		flushSync();
		expect(target.querySelector('#room-password')).not.toBeNull();
		expect(target.querySelector('dialog')).toBeNull();
		expect(target.querySelector('.list-row')).toBeNull();
		expect(data.openRoom).toHaveBeenCalledWith(fixture.room.slug, { hydrateSavedView: true });
	} finally {
		await unmount(component);
		target.remove();
		enrollment.mockRestore();
		vi.clearAllMocks();
	}
});
