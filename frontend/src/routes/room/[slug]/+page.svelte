<!--
	The room page (/app/room/{slug}). The folder name `[slug]` makes the slug a
	route parameter. The page asks for the password when the browser has no
	access, and shows the room once the data layer has loaded it.
-->
<script lang="ts">
	import { page } from '$app/state';
	import { closeRoom, logout, openRoom, type RoomHandle } from '#lib/data/index.ts';
	import RoomHeader from '#lib/room/RoomHeader.svelte';
	import RoomLogin from '#lib/room/RoomLogin.svelte';

	// `$derived` recomputes when what it reads changes (here: the URL).
	const slug = $derived(page.params.slug ?? '');

	let room = $state.raw<RoomHandle | null>(null);
	/** Bumped after signing out, so the effect below opens the room afresh. */
	let generation = $state(0);
	let logoutError = $state('');

	// Open the room while this page is shown. The function returned from an
	// effect runs before the effect runs again, and when the page is left.
	$effect(() => {
		void generation; // Read it, so a new value re-runs this effect.
		const handle = openRoom(slug);
		room = handle;
		return () => closeRoom(handle);
	});

	async function signOut() {
		const result = await logout(slug);
		if (!result.ok) {
			logoutError = result.message;
			return;
		}
		logoutError = '';
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
		<div class="card">
			<p>Could not verify room access. Please retry.</p>
			<button class="outline" type="button" onclick={() => room?.store.refresh()}>Retry</button>
		</div>
	{:else}
		<RoomHeader name={room.store.room?.name ?? ''} onLogout={signOut} />
		{#if logoutError}
			<p class="error" role="alert">{logoutError}</p>
		{/if}
	{/if}
</main>

<style>
	.error {
		color: var(--danger);
	}

	.card {
		display: grid;
		gap: var(--gap);
		justify-items: start;
	}
</style>
