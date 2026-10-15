// A "Deleted …" toast with an "Undo" button, for deletes that happen at once.
// When the delete fails, the toast goes away, so there is nothing to undo.

import { toasts } from './toasts.svelte.ts';

export interface UndoToastOptions {
	message: string;
	/** The delete request. Its failure dismisses the toast at once. */
	deleted: Promise<{ ok: boolean }>;
	/** How long "Undo" stays, in milliseconds. */
	duration: number;
	/** Whether "Undo" may run now; off while the room is read-only. */
	canUndo: () => boolean;
	/** Runs on "Undo". The caller shows the "Restored …" message. */
	undo: () => unknown;
}

/** Shows the undo toast (always red, as a delete). Returns its id. */
export function showUndoToast(options: UndoToastOptions): number {
	const toastId = toasts.show(options.message, 'danger', {
		duration: options.duration,
		action: {
			label: 'Undo',
			disabled: () => !options.canUndo(),
			run: () => void options.undo()
		}
	});
	void options.deleted.then((result) => {
		if (!result.ok) toasts.dismiss(toastId);
	});
	return toastId;
}
