import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	LiveUpdates,
	STALE_AFTER_HIDDEN,
	type LiveHost,
	type LiveState,
	type SessionState
} from './events';
import { FakeEventSource, FakeVisibility, settle } from './test-helpers';

function setup(session: SessionState = 'signed_in') {
	const states: LiveState[] = [];
	const host = {
		seq: 5,
		stale: false as boolean,
		refresh: vi.fn(async () => {}),
		authRequired: vi.fn(),
		liveChanged: (state: LiveState) => states.push(state)
	} satisfies LiveHost;
	const checkSession = vi.fn(async () => session);
	const onReconnect = vi.fn();
	const visibility = new FakeVisibility();
	const live = new LiveUpdates({
		url: '/api/v1/rooms/home/events',
		host,
		checkSession,
		onReconnect,
		createEventSource: (url) => new FakeEventSource(url),
		reconnectDelays: [1000, 5000],
		visibility: visibility as unknown as Document
	});
	return { host, checkSession, onReconnect, visibility, live, states };
}

describe('LiveUpdates', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		FakeEventSource.reset();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('refreshes when a seq event differs from the store seq', () => {
		const { host, live } = setup();
		live.start();
		const source = FakeEventSource.last;
		expect(source.url).toBe('/api/v1/rooms/home/events');

		source.open();
		source.seq(5);
		expect(host.refresh).not.toHaveBeenCalled();
		source.seq(6);
		expect(host.refresh).toHaveBeenCalledTimes(1);
		// Lower than ours: the database was restored.
		source.seq(2);
		expect(host.refresh).toHaveBeenCalledTimes(2);
	});

	it('refreshes and retries writes when the browser reconnects by itself', () => {
		const { host, onReconnect, live } = setup();
		live.start();
		const source = FakeEventSource.last;
		source.open();
		expect(host.refresh).not.toHaveBeenCalled();

		source.fail(true);
		source.open();
		expect(host.refresh).toHaveBeenCalledTimes(1);
		expect(onReconnect).toHaveBeenCalledTimes(1);
		expect(FakeEventSource.instances).toHaveLength(1);
	});

	it('reconnects with backoff when the stream closes for good', async () => {
		const { host, checkSession, live } = setup();
		live.start();
		FakeEventSource.last.fail(false);
		await settle();
		expect(checkSession).toHaveBeenCalledTimes(1);

		await vi.advanceTimersByTimeAsync(999);
		expect(FakeEventSource.instances).toHaveLength(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(FakeEventSource.instances).toHaveLength(2);

		FakeEventSource.last.fail(false);
		await settle();
		await vi.advanceTimersByTimeAsync(4999);
		expect(FakeEventSource.instances).toHaveLength(2);
		await vi.advanceTimersByTimeAsync(1);
		expect(FakeEventSource.instances).toHaveLength(3);

		FakeEventSource.last.open();
		expect(host.refresh).toHaveBeenCalledTimes(0); // first open of this run: the seq event follows
	});

	it('asks for sign-in when access is revoked', async () => {
		const { host, live } = setup('signed_out');
		live.start();
		const source = FakeEventSource.last;
		source.open();
		source.revoked();
		await settle();

		expect(source.closed).toBe(true);
		expect(host.authRequired).toHaveBeenCalledTimes(1);
		expect(live.running).toBe(false);
		await vi.advanceTimersByTimeAsync(60_000);
		expect(FakeEventSource.instances).toHaveLength(1);
	});

	it('reconnects after revoked when the session still works', async () => {
		const { host, live } = setup('signed_in');
		live.start();
		FakeEventSource.last.revoked();
		await settle();
		expect(host.authRequired).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(1000);
		expect(FakeEventSource.instances).toHaveLength(2);
	});

	it('catches up when the page becomes visible again', () => {
		const { host, onReconnect, visibility, live } = setup();
		live.start();
		const source = FakeEventSource.last;
		source.open();

		visibility.set('hidden');
		expect(host.refresh).not.toHaveBeenCalled();
		visibility.set('visible');
		expect(host.refresh).toHaveBeenCalledTimes(1);
		expect(onReconnect).toHaveBeenCalledTimes(1);
		expect(FakeEventSource.instances).toHaveLength(1);

		// A stream the phone dropped while hidden is opened again at once.
		source.close();
		visibility.set('visible');
		expect(FakeEventSource.instances).toHaveLength(2);
	});

	it('stops cleanly', async () => {
		const { host, visibility, live } = setup();
		live.start();
		const source = FakeEventSource.last;
		live.stop();

		expect(source.closed).toBe(true);
		source.seq(9);
		visibility.set('visible');
		await vi.advanceTimersByTimeAsync(60_000);
		expect(host.refresh).not.toHaveBeenCalled();
		expect(FakeEventSource.instances).toHaveLength(1);
	});

	it('reports its state for the connection indicator', async () => {
		const { live, states } = setup();
		live.start();
		expect(live.state).toBe('connecting');
		FakeEventSource.last.open();
		FakeEventSource.last.fail(true); // the browser retries
		FakeEventSource.last.open();
		FakeEventSource.last.fail(false); // closed: we retry after a pause
		await settle();
		expect(live.state).toBe('reconnecting');
		await vi.advanceTimersByTimeAsync(1000);
		FakeEventSource.last.open();
		live.stop();
		expect(states).toEqual([
			'connecting',
			'open',
			'reconnecting',
			'open',
			'reconnecting',
			'open',
			'stopped'
		]);
	});

	it('stops with state "stopped" when access is revoked', async () => {
		const { live, states } = setup('signed_out');
		live.start();
		FakeEventSource.last.open();
		FakeEventSource.last.revoked();
		await settle();
		expect(states.at(-1)).toBe('stopped');
	});

	it('reads again on an equal seq while the last read failed', () => {
		const { host, live } = setup();
		live.start();
		FakeEventSource.last.open();
		host.stale = true;
		FakeEventSource.last.seq(5);
		expect(host.refresh).toHaveBeenCalledTimes(1);
	});

	it('opens a new stream when the page was hidden for a while', () => {
		const { host, visibility, live } = setup();
		live.start();
		const first = FakeEventSource.last;
		first.open();

		visibility.set('hidden');
		vi.advanceTimersByTime(STALE_AFTER_HIDDEN - 1);
		visibility.set('visible');
		expect(FakeEventSource.instances).toHaveLength(1);

		visibility.set('hidden');
		vi.advanceTimersByTime(STALE_AFTER_HIDDEN);
		visibility.set('visible');
		expect(first.closed).toBe(true);
		expect(FakeEventSource.instances).toHaveLength(2);
		expect(host.refresh).toHaveBeenCalledTimes(2);
	});
});
