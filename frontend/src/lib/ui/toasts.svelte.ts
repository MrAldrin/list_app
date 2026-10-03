// Short messages at the bottom of the screen ("toasts"), like NiceGUI's
// `ui.notify`. Any page can call `toasts.show(…)`; `Toast.svelte` (in the
// root layout) shows them. A `.svelte.ts` file may use runes such as `$state`.

export type ToastKind = 'info' | 'success' | 'warning' | 'danger';

/** A button in a toast, such as "Undo". Pressing it also closes the toast. */
export interface ToastAction {
	label: string;
	run: () => void;
}

export interface ToastMessage {
	id: number;
	message: string;
	kind: ToastKind;
	action?: ToastAction;
}

export interface ToastOptions {
	action?: ToastAction;
	/** Milliseconds; the default is the store's duration. */
	duration?: number;
}

/** How long a toast stays, in milliseconds. */
export const TOAST_DURATION = 4_000;
/** Older toasts go when a new one would make more than this many. */
export const MAX_TOASTS = 3;

export class Toasts {
	/** The toasts on screen, oldest first. */
	items = $state.raw<readonly ToastMessage[]>([]);
	readonly #duration: number;
	#nextId = 0;

	constructor(duration = TOAST_DURATION) {
		this.#duration = duration;
	}

	/** Shows a message; it goes away by itself. Returns its id. */
	show(message: string, kind: ToastKind = 'info', options: ToastOptions = {}): number {
		this.#nextId += 1;
		const id = this.#nextId;
		const toast: ToastMessage = { id, message, kind };
		if (options.action) toast.action = options.action;
		this.items = [...this.items, toast].slice(-MAX_TOASTS);
		setTimeout(() => this.dismiss(id), options.duration ?? this.#duration);
		return id;
	}

	/** Closes the toast and runs its action. */
	act(id: number): void {
		const action = this.items.find((toast) => toast.id === id)?.action;
		this.dismiss(id);
		action?.run();
	}

	dismiss(id: number): void {
		this.items = this.items.filter((toast) => toast.id !== id);
	}
}

/** The one list of toasts for the whole app. */
export const toasts = new Toasts();
