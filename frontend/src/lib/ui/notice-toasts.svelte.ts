// Turns the data layer's messages (a rejected or failed change, such as
// "'milk' is already on the list") into warning toasts.

import { untrack } from 'svelte';
import type { RoomStore } from '#lib/data/index.ts';
import { toasts } from './toasts.svelte';

/** Call once while a page starts (it creates an `$effect`). */
export function showNoticesAsToasts(getStore: () => RoomStore | undefined): void {
	$effect(() => {
		const store = getStore();
		const notice = store?.notice;
		if (!store || !notice) return;
		// `untrack`: reading the toast list here must not re-run this effect.
		untrack(() => toasts.show(notice.message, 'warning'));
		store.dismissNotice();
	});
}
