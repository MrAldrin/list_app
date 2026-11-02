// Shows due-date reminders (src/lib/list/due-reminders.ts) as toasts while a
// room or share page is open. Browsers pause timers in background tabs, so the
// periodic check is reliable only while the app is on screen.

import { untrack } from 'svelte';
import type { RoomStore } from '#lib/data/index.ts';
import {
	clockNow,
	DUE_CHECK_INTERVAL_MS,
	DueReminders,
	type DueReminder
} from '#lib/list/due-reminders.ts';
import { toasts } from './toasts.svelte';

/** A reminder stays longer than a normal toast: it is worth reading. */
const DUE_TOAST_MS = 8_000;

function show(reminder: DueReminder | null): void {
	if (reminder) toasts.show(reminder.message, reminder.kind, { duration: DUE_TOAST_MS });
}

/**
 * Call once while a page starts (it creates `$effect`s). `getListUid` gives
 * the list on screen, or undefined on the room page.
 */
export function showDueReminders(
	getStore: () => RoomStore | undefined,
	getListUid: () => string | undefined
): void {
	let reminders = new DueReminders();
	let forStore: RoomStore | undefined;
	const ready = $derived(getStore()?.status === 'ready' ? getStore() : undefined);
	const remindersFor = (store: RoomStore) => {
		if (store !== forStore) {
			forStore = store;
			reminders = new DueReminders();
		}
		return reminders;
	};

	// Option 1: a list opens (or the page opens on a list).
	$effect(() => {
		const store = ready;
		const listUid = getListUid();
		if (!store || !listUid) return;
		untrack(() => show(remindersFor(store).listOpened(store.itemsOf(listUid), clockNow())));
	});

	// Option 2: all lists, now and every few minutes.
	$effect(() => {
		const store = ready;
		if (!store) return;
		const check = () =>
			untrack(() =>
				show(remindersFor(store).checkAll(store.lists, (uid) => store.itemsOf(uid), clockNow()))
			);
		// After the list-opened effect, so the open list is not counted twice.
		const first = setTimeout(check, 0);
		const timer = setInterval(check, DUE_CHECK_INTERVAL_MS);
		return () => {
			clearTimeout(first);
			clearInterval(timer);
		};
	});
}
