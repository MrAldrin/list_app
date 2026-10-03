import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { applied, deferred, settle, type Deferred } from './test-helpers';
import { ApiError, NetworkError } from './types';
import type { Op, OpResponse, SentOp } from './types';
import { WriteQueue, type QueueHost } from './write-queue';

const DELETE: Op = { type: 'list.delete', list_uid: 'l1' };
const op = (listUid: string): Op => ({ type: 'list.delete', list_uid: listUid });

/** A fake server: each `sendOp` call waits until the test answers it. */
function fakeSender() {
	const calls: { op: SentOp; answer: Deferred<OpResponse> }[] = [];
	return {
		calls,
		sendOp: vi.fn((_slug: string, sent: SentOp) => {
			const answer = deferred<OpResponse>();
			calls.push({ op: sent, answer });
			return answer.promise;
		})
	};
}

function fakeHost() {
	return {
		opQueued: vi.fn(),
		opSending: vi.fn(),
		opSettled: vi.fn(),
		opFailed: vi.fn(),
		opUnanswered: vi.fn(),
		authRequired: vi.fn()
	} satisfies QueueHost;
}

describe('WriteQueue', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('adds an op_id and sends ops in order, one at a time', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		const second = queue.send(op('b'));
		await settle();
		expect(sender.calls).toHaveLength(1);
		expect(sender.calls[0].op).toMatchObject({ type: 'list.delete', list_uid: 'a' });
		expect(sender.calls[0].op.op_id).toMatch(/^[0-9a-f-]{36}$/);
		expect(host.opQueued).toHaveBeenCalledTimes(2);

		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 1));
		expect(await first).toMatchObject({ status: 'applied', seq: 1 });
		await settle();
		expect(sender.calls).toHaveLength(2);
		expect(sender.calls[1].op).toMatchObject({ list_uid: 'b' });
		expect(sender.calls[1].op.op_id).not.toBe(sender.calls[0].op.op_id);

		sender.calls[1].answer.resolve(applied(sender.calls[1].op, 2));
		await second;
		expect(queue.pending).toHaveLength(0);
	});

	it('tells the host when an answer is open and when it comes', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const sent = queue.send(DELETE);
		await settle();
		expect(host.opSending).toHaveBeenCalledWith(sender.calls[0].op);
		expect(host.opSettled).not.toHaveBeenCalled();

		sender.calls[0].answer.resolve(applied(sender.calls[0].op, 6));
		await sent;
		expect(host.opSettled).toHaveBeenCalledWith(sender.calls[0].op, applied(sender.calls[0].op, 6));
	});

	it('retries the same op_id after a network error or 503, keeping the order', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host, { retryDelays: [1000, 5000] });

		const first = queue.send(op('a'));
		void queue.send(op('b'));
		await settle();
		sender.calls[0].answer.reject(new NetworkError());
		await settle();
		expect(sender.calls).toHaveLength(1);
		expect(host.opUnanswered).toHaveBeenCalledWith(sender.calls[0].op, true);

		await vi.advanceTimersByTimeAsync(1000);
		expect(sender.calls).toHaveLength(2);
		expect(sender.calls[1].op).toEqual(sender.calls[0].op);

		sender.calls[1].answer.reject(new ApiError(503, 'unavailable', 'busy'));
		await vi.advanceTimersByTimeAsync(4999);
		expect(sender.calls).toHaveLength(2);
		await vi.advanceTimersByTimeAsync(1);
		expect(sender.calls).toHaveLength(3);
		expect(sender.calls[2].op.op_id).toBe(sender.calls[0].op.op_id);

		sender.calls[2].answer.resolve(applied(sender.calls[2].op, 1));
		await first;
		await settle();
		expect(sender.calls[3].op).toMatchObject({ list_uid: 'b' });
		expect(host.opFailed).not.toHaveBeenCalled();
	});

	it('retries at once on retryNow', async () => {
		const sender = fakeSender();
		const queue = new WriteQueue('home', sender, fakeHost(), { retryDelays: [30_000] });

		void queue.send(DELETE);
		await settle();
		sender.calls[0].answer.reject(new NetworkError());
		await settle();
		queue.retryNow();
		await settle();
		expect(sender.calls).toHaveLength(2);
	});

	it('pauses on 401 and sends the waiting ops after resume', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		void queue.send(op('b'));
		await settle();
		sender.calls[0].answer.reject(new ApiError(401, 'not_authenticated', 'Sign in.'));
		await settle();

		expect(host.authRequired).toHaveBeenCalledTimes(1);
		expect(host.opUnanswered).toHaveBeenCalledWith(sender.calls[0].op, false);
		expect(queue.paused).toBe(true);
		expect(queue.pending).toHaveLength(2);
		void queue.send(op('c'));
		await vi.advanceTimersByTimeAsync(60_000);
		expect(sender.calls).toHaveLength(1);

		queue.resume();
		await settle();
		expect(sender.calls).toHaveLength(2);
		expect(sender.calls[1].op).toEqual(sender.calls[0].op);
		sender.calls[1].answer.resolve(applied(sender.calls[1].op, 1));
		await first;
		await settle();
		expect(sender.calls[2].op).toMatchObject({ list_uid: 'b' });
	});

	it.each([403, 409, 415, 422, 500])('fails the op on %s and goes on', async (status) => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		const second = queue.send(op('b'));
		await settle();
		const error = new ApiError(status, 'invalid_request', 'Nope.');
		sender.calls[0].answer.reject(error);

		await expect(first).rejects.toBe(error);
		expect(host.opFailed).toHaveBeenCalledWith(sender.calls[0].op, error);
		await settle();
		expect(sender.calls[1].op).toMatchObject({ list_uid: 'b' });
		sender.calls[1].answer.resolve(applied(sender.calls[1].op, 1));
		await expect(second).resolves.toMatchObject({ status: 'applied' });
	});

	it('resolves rejected answers and goes on', async () => {
		const sender = fakeSender();
		const host = fakeHost();
		const queue = new WriteQueue('home', sender, host);

		const first = queue.send(op('a'));
		await settle();
		const rejected: OpResponse = {
			op_id: sender.calls[0].op.op_id,
			status: 'rejected',
			code: 'list_unavailable',
			message: 'The list is no longer available.',
			seq: 0
		};
		sender.calls[0].answer.resolve(rejected);
		expect(await first).toEqual(rejected);
		expect(host.opSettled).toHaveBeenCalledWith(sender.calls[0].op, rejected);
	});

	it('rejects every queued op on dispose', async () => {
		const sender = fakeSender();
		const queue = new WriteQueue('home', sender, fakeHost());
		const first = queue.send(op('a'));
		const second = queue.send(op('b'));
		const reason = new Error('Signed out.');

		queue.dispose(reason);
		await expect(first).rejects.toBe(reason);
		await expect(second).rejects.toBe(reason);
		expect(queue.pending).toHaveLength(0);
		await expect(queue.send(op('c'))).rejects.toThrow('closed');
	});
});
