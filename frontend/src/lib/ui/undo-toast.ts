// A toast with an "Undo" button, for changes that happen at once, such as
// "Deleted …" or "Checked …". When the change fails, the toast goes away, so
// there is nothing to undo.

import { toasts, type ToastKind } from './toasts.svelte.ts';

export interface UndoToastOptions {
	message: string;
	/** The change request. Its failure dismisses the toast at once. */
	request: Promise<{ ok: boolean }>;
	/** The toast's color; red (a delete) unless given. */
	kind?: ToastKind;
	/** How long "Undo" stays, in milliseconds. */
	duration: number;
	/** Whether "Undo" may run now; off while the room is read-only. */
	canUndo: () => boolean;
	/** Runs on "Undo". The caller shows any "Restored …" message. */
	undo: () => unknown;
}

/** Shows the undo toast. Returns its id. */
export function showUndoToast(options: UndoToastOptions): number {
	const toastId = toasts.show(options.message, options.kind ?? 'danger', {
		duration: options.duration,
		action: {
			label: 'Undo',
			disabled: () => !options.canUndo(),
			run: () => void options.undo()
		}
	});
	void options.request.then((result) => {
		if (!result.ok) toasts.dismiss(toastId);
	});
	return toastId;
}
