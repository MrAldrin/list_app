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
	import PageShell from '#lib/room/PageShell.svelte';

	const roomSlug = $derived(page.params.slug ?? '');
	const listSlug = $derived(page.params.list ?? '');
	const roomHref = $derived(resolve('/room/[slug]', { slug: roomSlug }));

	let room = $state.raw<RoomHandle | null>(null);

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

<PageShell
	bind:handle={room}
	open={() => openRoom(roomSlug, { hydrateSavedView: true })}
	close={closeRoom}
	canSignIn
	connectTitle="Connect to load this list."
	failedTitle="Could not load this list."
>
	{#snippet content(handle)}
		{#if !list}
			<div class="card problem" role="status">
				<p>{shownSlug === listSlug ? DELETED_LIST_MESSAGE : UNAVAILABLE_LIST_MESSAGE}</p>
				<a class="back" href={roomHref}>Back to room</a>
			</div>
		{:else}
			<ListView room={handle} {list} {roomHref} canReset />
		{/if}
	{/snippet}
</PageShell>

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
