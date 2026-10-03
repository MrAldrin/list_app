// Short messages at the bottom of the screen ("toasts"), like NiceGUI's
// `ui.notify`. Any page can call `toasts.show(…)`; `Toast.svelte` (in the
// root layout) shows them. A `.svelte.ts` file may use runes such as `$state`.

export type ToastKind = 'info' | 'success' | 'warning' | 'danger';

export interface ToastMessage {
	id: number;
	message: string;
	kind: ToastKind;
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
	show(message: string, kind: ToastKind = 'info'): number {
		this.#nextId += 1;
		const id = this.#nextId;
		this.items = [...this.items, { id, message, kind }].slice(-MAX_TOASTS);
		setTimeout(() => this.dismiss(id), this.#duration);
		return id;
	}

	dismiss(id: number): void {
		this.items = this.items.filter((toast) => toast.id !== id);
	}
}

/** The one list of toasts for the whole app. */
export const toasts = new Toasts();
