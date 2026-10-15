// Keeps the focus where it is when a button is pressed.

/**
 * For `onpointerdown` and `onmousedown` on a button next to a field. Pressing a
 * button would move the focus away from the field (and close the phone
 * keyboard); stopping the press's default keeps it in the field.
 */
export function keepFocus(event: Event): void {
	event.preventDefault();
}
