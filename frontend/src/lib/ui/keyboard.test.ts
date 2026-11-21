// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { watchKeyboardInset } from './keyboard';

class TestViewport extends EventTarget {
	height = 800;
	offsetTop = 0;
}

describe('watchKeyboardInset', () => {
	let viewport: TestViewport;
	let stop: (() => void) | undefined;
	const report = vi.fn<(inset: number) => void>();

	beforeEach(() => {
		viewport = new TestViewport();
		vi.stubGlobal('visualViewport', viewport);
		vi.stubGlobal('innerHeight', 800);
		vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame'] });
		report.mockClear();
	});

	afterEach(() => {
		stop?.();
		stop = undefined;
		document.body.replaceChildren();
		vi.useRealTimers();
		vi.unstubAllGlobals();
	});

	function focus(markup: string): HTMLElement {
		document.body.innerHTML = markup;
		const field = document.body.querySelector<HTMLElement>(':scope > *');
		if (!field) throw new Error('Missing focus target');
		field.focus();
		expect(document.activeElement).toBe(field);
		return field;
	}

	it('ignores overscroll, including while the add field stays focused', () => {
		stop = watchKeyboardInset(report);
		viewport.offsetTop = -357;
		viewport.dispatchEvent(new Event('scroll'));
		expect(report).toHaveBeenLastCalledWith(0);

		focus('<input type="search">');
		vi.advanceTimersToNextFrame();
		expect(report).toHaveBeenLastCalledWith(0);
	});

	it('ignores small browser-bar shifts while an editable element has focus', () => {
		focus('<input>');
		stop = watchKeyboardInset(report);
		viewport.height = 700;
		viewport.dispatchEvent(new Event('resize'));
		expect(report).toHaveBeenLastCalledWith(0);
	});

	it.each(['<button></button>', '<input type="checkbox">', '<input readonly>'])(
		'ignores a large height change when %s has focus',
		(markup) => {
			focus(markup);
			viewport.height = 500;
			stop = watchKeyboardInset(report);
			expect(report).toHaveBeenLastCalledWith(0);
		}
	);

	it.each(['<input type="search">', '<textarea></textarea>', '<div contenteditable="true"></div>'])(
		'updates the inset on focus, viewport moves and blur for %s',
		(markup) => {
			viewport.height = 500;
			stop = watchKeyboardInset(report);
			expect(report).toHaveBeenLastCalledWith(0);

			const field = focus(markup);
			vi.advanceTimersToNextFrame();
			expect(report).toHaveBeenLastCalledWith(300);

			viewport.offsetTop = 40;
			viewport.dispatchEvent(new Event('scroll'));
			expect(report).toHaveBeenLastCalledWith(260);

			viewport.height = 550;
			viewport.dispatchEvent(new Event('resize'));
			expect(report).toHaveBeenLastCalledWith(210);

			field.blur();
			vi.advanceTimersToNextFrame();
			expect(report).toHaveBeenLastCalledWith(0);
		}
	);

	it('reports zero if the browser has no visual viewport API', () => {
		vi.stubGlobal('visualViewport', null);
		stop = watchKeyboardInset(report);
		expect(report).toHaveBeenCalledExactlyOnceWith(0);
	});

	it('removes listeners and cancels a pending focus update on cleanup', () => {
		const cleanup = watchKeyboardInset(report);
		const field = focus('<input>');
		cleanup?.();
		field.blur();
		viewport.dispatchEvent(new Event('resize'));
		viewport.dispatchEvent(new Event('scroll'));
		vi.advanceTimersToNextFrame();
		expect(report).toHaveBeenCalledExactlyOnceWith(0);
	});
});
