import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MAX_TOASTS, Toasts } from './toasts.svelte';

describe('Toasts', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});
	afterEach(() => {
		vi.useRealTimers();
	});

	it('shows a toast and removes it after the duration', () => {
		const toasts = new Toasts(1_000);
		toasts.show('List created', 'success');
		expect(toasts.items).toEqual([{ id: 1, message: 'List created', kind: 'success' }]);
		vi.advanceTimersByTime(999);
		expect(toasts.items).toHaveLength(1);
		vi.advanceTimersByTime(1);
		expect(toasts.items).toEqual([]);
	});

	it('defaults to info and gives each toast its own id', () => {
		const toasts = new Toasts();
		const first = toasts.show('one');
		const second = toasts.show('two');
		expect(second).not.toBe(first);
		expect(toasts.items.map((toast) => toast.kind)).toEqual(['info', 'info']);
	});

	it('dismisses one toast and leaves the others', () => {
		const toasts = new Toasts();
		const first = toasts.show('one');
		toasts.show('two');
		toasts.dismiss(first);
		expect(toasts.items.map((toast) => toast.message)).toEqual(['two']);
	});

	it(`keeps at most ${MAX_TOASTS}, dropping the oldest`, () => {
		const toasts = new Toasts();
		for (const message of ['a', 'b', 'c', 'd']) toasts.show(message);
		expect(toasts.items.map((toast) => toast.message)).toEqual(['b', 'c', 'd']);
		// The timer of a dropped toast does nothing harmful later.
		vi.runAllTimers();
		expect(toasts.items).toEqual([]);
	});
});
