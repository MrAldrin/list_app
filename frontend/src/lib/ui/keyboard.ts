const KEYBOARD_MIN_HEIGHT = 100;
const TEXT_INPUT_TYPES = new Set(['email', 'number', 'password', 'search', 'tel', 'text', 'url']);

function isEditable(element: Element | null): boolean {
	if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement) {
		return (
			!element.readOnly &&
			!element.matches(':disabled') &&
			(element instanceof HTMLTextAreaElement || TEXT_INPUT_TYPES.has(element.type))
		);
	}
	return element instanceof HTMLElement && element.isContentEditable;
}

/** Report the bottom inset in CSS pixels while an on-screen keyboard covers the page. */
export function watchKeyboardInset(onChange: (inset: number) => void): (() => void) | undefined {
	const viewport = window.visualViewport;
	if (!viewport) {
		onChange(0);
		return;
	}

	const update = () => {
		// iOS can report a negative offsetTop during rubber-band scrolling.
		// Do not count that movement as part of the covered height.
		const covered = window.innerHeight - viewport.height - Math.max(0, viewport.offsetTop);
		onChange(covered > KEYBOARD_MIN_HEIGHT && isEditable(document.activeElement) ? covered : 0);
	};
	let frame = 0;
	const updateAfterFocus = () => {
		// Read the new active element after focus has moved, not during focusout.
		window.cancelAnimationFrame(frame);
		frame = window.requestAnimationFrame(update);
	};

	update();
	viewport.addEventListener('resize', update);
	viewport.addEventListener('scroll', update);
	document.addEventListener('focusin', updateAfterFocus);
	document.addEventListener('focusout', updateAfterFocus);
	return () => {
		viewport.removeEventListener('resize', update);
		viewport.removeEventListener('scroll', update);
		document.removeEventListener('focusin', updateAfterFocus);
		document.removeEventListener('focusout', updateAfterFocus);
		window.cancelAnimationFrame(frame);
	};
}
