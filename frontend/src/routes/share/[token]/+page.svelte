<!--
	A share link (/app/share/{token}): one list, to view and edit without the
	room password (docs/public-sharing.md). It never opens the room: there is
	no back link and no "Reset share link". When the link is reset or the list
	is deleted, the page says so and the list goes away.
-->
<script lang="ts">
	import { page } from '$app/state';
	import { closeShare, openShare, type RoomHandle } from '#lib/data/index.ts';
	import { SHARE_RESET_MESSAGE, SHARE_UNAVAILABLE_MESSAGE } from '#lib/list/items.ts';
	import ListView from '#lib/list/ListView.svelte';
	import ConnectionStatus from '#lib/ui/ConnectionStatus.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { showNoticesAsToasts } from '#lib/ui/notice-toasts.svelte.ts';

	const token = $derived(page.params.token ?? '');

	let share = $state.raw<RoomHandle | null>(null);

	// Open the link while this page is shown (like a room on the room page).
	$effect(() => {
		const handle = openShare(token);
		share = handle;
		return () => closeShare(handle);
	});

	showNoticesAsToasts(() => share?.store);

	// The feed of a share link holds exactly one list.
	const list = $derived(share?.store.status === 'ready' ? share.store.lists[0] : undefined);

	// The link this page has shown a list for. If the list then goes, the
	// link was reset or the list deleted; on load it may also be a wrong link.
	let shownToken = $state<string | null>(null);
	$effect(() => {
		if (list) shownToken = token;
	});
</script>

<svelte:head>
	<title>{list?.name ?? 'List'} – ListR</title>
</svelte:head>

<main class="page">
	{#if !share || share.store.status === 'loading'}
		<p class="muted">Loading…</p>
	{:else if share.store.status === 'error'}
		<LoadError
			title="Could not load this list."
			detail={share.store.error}
			onRetry={() => share!.store.refresh()}
		/>
	{:else if !list}
		<div class="card problem" role="status">
			<p>{shownToken === token ? SHARE_RESET_MESSAGE : SHARE_UNAVAILABLE_MESSAGE}</p>
		</div>
	{:else}
		<ListView room={share} {list} roomHref={null} canReset={false} />
	{/if}
	{#if share && share.store.status !== 'auth_required'}
		<ConnectionStatus store={share.store} />
	{/if}
</main>

<style>
	.problem {
		text-align: center;
		margin-bottom: 1rem;
	}
</style>
