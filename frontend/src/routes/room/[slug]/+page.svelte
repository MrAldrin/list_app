<!--
	The room page (/room/{slug}). The folder name `[slug]` makes the slug a
	route parameter. The page asks for the password when the browser has no
	access, and shows the room's lists once the data layer has loaded them.
-->
<script lang="ts">
	import { page } from '$app/state';
	import { admin, closeRoom, logout, openRoom, type RoomHandle } from '#lib/data/index.ts';
	import RoomHeader from '#lib/room/RoomHeader.svelte';
	import RoomLists from '#lib/room/RoomLists.svelte';
	import RoomLogin from '#lib/room/RoomLogin.svelte';
	import ConnectionStatus from '#lib/ui/ConnectionStatus.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { showNoticesAsToasts } from '#lib/ui/notice-toasts.svelte.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	// `$derived` recomputes when what it reads changes (here: the URL).
	const slug = $derived(page.params.slug ?? '');

	let room = $state.raw<RoomHandle | null>(null);
	/** Bumped after signing out, so the effect below opens the room afresh. */
	let generation = $state(0);

	// Open the room while this page is shown. The function returned from an
	// effect runs before the effect runs again, and when the page is left.
	$effect(() => {
		void generation; // Read it, so a new value re-runs this effect.
		const handle = openRoom(slug);
		room = handle;
		return () => closeRoom(handle);
	});

	// A browser signed in as admin gets a way back to the admin page in the
	// header, also after opening a list and coming back. It never gives room
	// access. A browser that is not signed in as admin sees the normal header.
	let isAdmin = $state(false);
	$effect(() => {
		void slug; // Ask again when another room opens.
		isAdmin = false;
		let current = true;
		admin
			.signedIn()
			.then((signedIn) => {
				if (current) isAdmin = signedIn;
			})
			.catch(() => undefined); // Without an answer, keep the normal header.
		return () => {
			current = false;
		};
	});

	// Messages from the data layer (a rejected or failed change) become toasts.
	showNoticesAsToasts(() => room?.store);

	async function signOut() {
		const result = await logout(slug);
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			return;
		}
		// The old room data is gone; opening again shows the password prompt.
		generation += 1;
	}
</script>

<svelte:head>
	<title>{room?.store.room?.name ?? 'Room'} – ListR</title>
</svelte:head>

<main class="page">
	{#if !room || room.store.status === 'loading'}
		<p class="muted">Loading…</p>
	{:else if room.store.status === 'auth_required'}
		<RoomLogin onLogin={(password) => room!.login(password)} />
	{:else if room.store.status === 'error'}
		<!-- The first load failed (server down or busy). It also retries by
		     itself when the live stream gets through again. -->
		<LoadError
			title="Could not load this room."
			detail={room.store.error}
			onRetry={() => room!.store.refresh()}
		/>
	{:else}
		<RoomHeader {room} backToAdmin={isAdmin} onLogout={signOut} />
		{#if room.store.error}
			<!-- The lists below may be out of date; they stay usable. -->
			<LoadError
				title="Could not load the latest changes."
				detail={room.store.error}
				onRetry={() => room!.store.refresh()}
			/>
		{/if}
		<RoomLists {room} />
	{/if}
	{#if room && room.store.status !== 'auth_required'}
		<ConnectionStatus store={room.store} />
	{/if}
</main>
