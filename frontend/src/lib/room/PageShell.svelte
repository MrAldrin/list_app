<!--
	The frame of the pages that show one room or one share link: the room
	page, a list in a room, and a share link. It opens the handle while the page
	is shown and closes it when the page is left. Then it shows, in order: the
	"Loading…" text, the saved-view notice, the sign-in prompt (rooms only), the
	load error with Retry, or the page's own content (passed as `content`, with
	the loaded handle as its argument). The connection status and the toasts for
	data-layer messages are shown here too.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { RoomHandle } from '#lib/data/index.ts';
	import ConnectionStatus from '#lib/ui/ConnectionStatus.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import SavedViewNotice from '#lib/ui/SavedViewNotice.svelte';
	import { showNoticesAsToasts } from '#lib/ui/notice-toasts.svelte.ts';
	import RoomLogin from './RoomLogin.svelte';

	let {
		handle = $bindable(null),
		open,
		close,
		reopenKey = 0,
		canSignIn = false,
		connectTitle,
		failedTitle,
		content
	}: {
		/** The opened handle, for the page's own use (for example its title). */
		handle?: RoomHandle | null;
		/** Opens the room or share link, for example `openRoom(slug, …)`. */
		open: () => RoomHandle;
		close: (handle: RoomHandle) => void;
		/** Opens again when this changes (the room page does so after sign-out). */
		reopenKey?: number;
		/** Whether the password prompt may show (not for share links). */
		canSignIn?: boolean;
		/** Load error title when there is no saved copy and the server is out of reach. */
		connectTitle: string;
		/** Load error title for any other failure. */
		failedTitle: string;
		content: Snippet<[RoomHandle]>;
	} = $props();

	// Open while the page is shown. The function returned from an effect runs
	// before the effect runs again, and when the page is left.
	$effect(() => {
		void reopenKey; // Read it, so a new value re-runs this effect.
		const opened = open();
		handle = opened;
		return () => close(opened);
	});

	// Messages from the data layer (a rejected or failed change) become toasts.
	showNoticesAsToasts(() => handle?.store);
</script>

<main class="page">
	{#if !handle || handle.store.status === 'loading'}
		<p class="muted">Loading…</p>
	{:else}
		<SavedViewNotice room={handle} />
		{#if handle.store.status === 'auth_required' && canSignIn}
			<RoomLogin onLogin={(password) => handle!.login(password)} />
		{:else if handle.store.status === 'error'}
			<!-- The first load failed (server down or busy). It also retries by
			     itself when the live stream gets through again. -->
			<LoadError
				title={!handle.store.savedAt && handle.store.unreachable ? connectTitle : failedTitle}
				detail={handle.store.error}
				onRetry={() => handle!.store.refresh()}
			/>
		{:else}
			{@render content(handle)}
		{/if}
	{/if}
	{#if handle && handle.store.status !== 'auth_required'}
		<ConnectionStatus store={handle.store} />
	{/if}
</main>
