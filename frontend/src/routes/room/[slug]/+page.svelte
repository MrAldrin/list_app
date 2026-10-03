<!--
	The room page (/app/room/{slug}). The folder name `[slug]` makes the slug a
	route parameter. The page asks for the password when the browser has no
	access, and shows the room's lists once the data layer has loaded them.
-->
<script lang="ts">
	import { untrack } from 'svelte';
	import { page } from '$app/state';
	import { closeRoom, logout, openRoom, type RoomHandle } from '#lib/data/index.ts';
	import RoomHeader from '#lib/room/RoomHeader.svelte';
	import RoomLists from '#lib/room/RoomLists.svelte';
	import RoomLogin from '#lib/room/RoomLogin.svelte';
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

	// Messages from the data layer (a rejected or failed change) become toasts.
	$effect(() => {
		const store = room?.store;
		const notice = store?.notice;
		if (!store || !notice) return;
		// `untrack`: reading the toast list here must not re-run this effect.
		untrack(() => toasts.show(notice.message, 'warning'));
		store.dismissNotice();
	});

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
		<div class="card problem">
			<p>Could not verify room access. Please retry.</p>
			<button class="outline" type="button" onclick={() => room?.store.refresh()}>Retry</button>
		</div>
	{:else}
		<RoomHeader name={room.store.room?.name ?? ''} onLogout={signOut} />
		{#if room.store.error}
			<!-- The lists below may be out of date; they stay usable. -->
			<div class="card problem" role="status">
				<p>Could not load the latest changes.</p>
				<button class="outline" type="button" onclick={() => room?.store.refresh()}>Retry</button>
			</div>
		{/if}
		<RoomLists {room} />
	{/if}
</main>

<style>
	.problem {
		display: grid;
		gap: var(--gap);
		justify-items: start;
		margin-bottom: 1rem;
	}
</style>
