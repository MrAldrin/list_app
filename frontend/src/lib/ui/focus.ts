// Keeps the focus where it is when a nearby control is pressed.

/**
 * For `onpointerdown` and `onmousedown` on a control next to a field. Stopping
 * the press's default keeps focus in the field, so its phone keyboard stays open.
 */
export function keepFocus(event: Event): void {
	event.preventDefault();
}
