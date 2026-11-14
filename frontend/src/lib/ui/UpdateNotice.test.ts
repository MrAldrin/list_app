// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { afterEach, expect, it } from 'vitest';
import { Api } from '#lib/data/api.ts';
import { compat, EXPECTED_API_VERSION, resetCompat } from '#lib/data/compat.svelte.ts';
import { deferred, fakeFetch, json, makeFeed, makeList, waitFor } from '#lib/data/test-helpers.ts';
import type { SentOp } from '#lib/data/types.ts';
import { readyRoom } from '#lib/test-support/room-fixture.ts';
import UpdateNotice from './UpdateNotice.svelte';

afterEach(resetCompat);

it('compatible headerless replies show no alert', async () => {
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(UpdateNotice, { target });
	const replies = [deferred<Response>(), deferred<Response>()];
	const fetch = fakeFetch();
	for (const reply of replies) fetch.mockImplementationOnce(() => reply.promise);
	const api = new Api(fetch);
	try {
		flushSync();
		for (const [index, name] of ['milk', 'bread'].entries()) {
			const op: SentOp = { op_id: `op-${index}`, type: 'item.add', list_uid: 'groceries', name };
			const pending = api.sendOp('home', op);
			expect(fetch).toHaveBeenCalledTimes(index + 1);
			expect(target.querySelector('[role="alert"]')).toBeNull();
			const result = {
				op_id: op.op_id,
				status: 'applied',
				seq: index + 1,
				result: { outcome: 'created' }
			};
			replies[index].resolve(json(200, result));
			expect(await pending).toEqual(result);
			flushSync();
			expect(compat.incompatible).toBe(false);
			expect(target.querySelector('[role="alert"]')).toBeNull();
		}
	} finally {
		await unmount(component);
		target.remove();
	}
});

it('503 mismatch reports one durable unsent change', async () => {
	const list = makeList();
	const fixture = await readyRoom(makeFeed({ full: true, lists: [list] }));
	const response = json(503, { error: { code: 'unavailable', message: 'Busy' } });
	response.headers.set('X-Api-Version', String(EXPECTED_API_VERSION + 1));
	const fetch = fakeFetch(response);
	const api = new Api(fetch);
	fixture.api.sendOp.mockImplementation((slug, op) => api.sendOp(slug, op));
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(UpdateNotice, { target });
	try {
		flushSync();
		expect(target.querySelector('[role="alert"]')).toBeNull();
		// Online edits wait for an applied response. A retryable 503 leaves
		// that promise pending; observe the persisted queue, not completion.
		let answered = false;
		void fixture.room.addItem(list, 'milk').then(() => {
			answered = true;
		});
		await waitFor(async () => {
			expect(compat.incompatible).toBe(true);
			expect(await fixture.queue.read()).toHaveLength(1);
			expect(compat.waitingWrites).toBe(1);
			expect(compat.unsavedWrites).toBe(0);
		});
		flushSync();
		const alert = target.querySelector('[role="alert"]')!;
		expect(alert).not.toBeNull();
		expect(alert.querySelector('.warning')?.textContent?.trim()).toBe(
			'1 change is saved on this phone and is not sent yet.'
		);
		expect(alert.textContent).not.toContain('will lose');
		expect(compat.incompatible).toBe(true);
		expect(fixture.room.changesDurable).toBe(true);
		const [stored] = await fixture.queue.read();
		expect(stored.op).toMatchObject({ type: 'item.add', name: 'milk', list_uid: list.uid });
		expect(fixture.room.queuedOps).toEqual([stored.op]);
		expect(answered).toBe(false);
		expect(fixture.room.store.seq).toBe(1);
		expect(fixture.room.store.pendingOps).toHaveLength(1);
		expect(fetch).toHaveBeenCalledTimes(1);
		expect(JSON.parse(fetch.mock.calls[0][1]?.body as string)).toEqual(stored.op);
		expect(fixture.room.store.notSaved).toEqual([]);
	} finally {
		await unmount(component);
		fixture.room.release();
		target.remove();
	}
});
