<!--
	The list page (/room/{room}/list/{list}). The room is in the URL because
	the data layer loads a whole room at once (the changes feed is per room).
	The page asks for the room password when needed, like the room page, and
	shows a clear message when the list is gone or not in this room.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { closeRoom, openRoom, type RoomHandle } from '#lib/data/index.ts';
	import { DELETED_LIST_MESSAGE, UNAVAILABLE_LIST_MESSAGE } from '#lib/list/items.ts';
	import ListView from '#lib/list/ListView.svelte';
	import RoomLogin from '#lib/room/RoomLogin.svelte';
	import ConnectionStatus from '#lib/ui/ConnectionStatus.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { showNoticesAsToasts } from '#lib/ui/notice-toasts.svelte.ts';

	const roomSlug = $derived(page.params.slug ?? '');
	const listSlug = $derived(page.params.list ?? '');
	const roomHref = $derived(resolve('/room/[slug]', { slug: roomSlug }));

	let room = $state.raw<RoomHandle | null>(null);

	// Open the room while this page is shown (see the room page).
	$effect(() => {
		const handle = openRoom(roomSlug);
		room = handle;
		return () => closeRoom(handle);
	});

	showNoticesAsToasts(() => room?.store);

	const list = $derived(room?.store.listBySlug(listSlug));

	// The list this page has shown. If it then goes missing, it was deleted;
	// a list that was never there may also be a wrong link.
	let shownSlug = $state<string | null>(null);
	$effect(() => {
		if (list) shownSlug = listSlug;
	});
</script>

<svelte:head>
	<title>{list?.name ?? 'List'} – ListR</title>
</svelte:head>

<main class="page">
	{#if !room || room.store.status === 'loading'}
		<p class="muted">Loading…</p>
	{:else if room.store.status === 'auth_required'}
		<RoomLogin onLogin={(password) => room!.login(password)} />
	{:else if room.store.status === 'error'}
		<LoadError
			title="Could not load this list."
			detail={room.store.error}
			onRetry={() => room!.store.refresh()}
		/>
	{:else if !list}
		<div class="card problem" role="status">
			<p>{shownSlug === listSlug ? DELETED_LIST_MESSAGE : UNAVAILABLE_LIST_MESSAGE}</p>
			<a class="back" href={roomHref}>Back to room</a>
		</div>
	{:else}
		<ListView {room} {list} {roomHref} canReset />
	{/if}
	{#if room && room.store.status !== 'auth_required'}
		<ConnectionStatus store={room.store} />
	{/if}
</main>

<style>
	.problem {
		display: grid;
		gap: var(--gap);
		justify-items: center;
		text-align: center;
		margin-bottom: 1rem;
	}

	/* A link that looks like an outlined button, as in NiceGUI. It stays a
	   link because it goes to another page. */
	.back {
		display: inline-flex;
		align-items: center;
		min-height: var(--touch);
		padding: 0 1rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		font-weight: 600;
		text-decoration: none;
	}
</style>
