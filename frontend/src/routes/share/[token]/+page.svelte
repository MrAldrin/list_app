<!--
	A share link (/share/{token}): one list, to view and edit without the
	room password (docs/public-sharing.md). The link never opens the room. Only
	a browser that already has access to the list's room (the server says so in
	the feed's `room`) gets the back arrow and "Reset share link"; everyone
	else sees nothing about the room. When the link is reset or the list is
	deleted, the page says so and the list goes away.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { closeShare, openShare, type RoomHandle } from '#lib/data/index.ts';
	import { SHARE_RESET_MESSAGE, SHARE_UNAVAILABLE_MESSAGE } from '#lib/list/items.ts';
	import ListView from '#lib/list/ListView.svelte';
	import ConnectionStatus from '#lib/ui/ConnectionStatus.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import SavedViewNotice from '#lib/ui/SavedViewNotice.svelte';
	import { showNoticesAsToasts } from '#lib/ui/notice-toasts.svelte.ts';

	const token = $derived(page.params.token ?? '');

	let share = $state.raw<RoomHandle | null>(null);

	// Open the link while this page is shown (like a room on the room page).
	$effect(() => {
		const handle = openShare(token, { hydrateSavedView: true });
		share = handle;
		return () => closeShare(handle);
	});

	showNoticesAsToasts(() => share?.store);

	// The feed of a share link holds exactly one list.
	const list = $derived(share?.store.status === 'ready' ? share.store.lists[0] : undefined);

	// The link this page has shown a list for. If the list then goes, the
	// link was reset or the list deleted; on load it may also be a wrong link.
	let shownToken = $state<string | null>(null);
	// The room, when this browser may open it. Kept when the list goes away,
	// so the message can still offer the way back.
	let memberRoomSlug = $state<string | null>(null);
	$effect(() => {
		if (!list) return;
		shownToken = token;
		memberRoomSlug = share?.store.room?.slug ?? null;
	});
	const roomHref = $derived(
		memberRoomSlug && share && !share.store.readOnly
			? resolve('/room/[slug]', { slug: memberRoomSlug })
			: null
	);

	// The old link is gone after a reset: follow the new one.
	function followReset(newToken: string) {
		void goto(resolve('/share/[token]', { token: newToken }), { replaceState: true });
	}
</script>

<svelte:head>
	<title>{list?.name ?? 'List'} – ListR</title>
</svelte:head>

<main class="page">
	{#if !share || share.store.status === 'loading'}
		<p class="muted">Loading…</p>
	{:else if share.store.status === 'error'}
		<SavedViewNotice room={share} />
		<LoadError
			title={!share.store.savedAt && share.store.unreachable
				? 'Connect to load this shared list.'
				: 'Could not load this list.'}
			detail={share.store.error}
			onRetry={() => share!.store.refresh()}
		/>
	{:else if !list}
		<SavedViewNotice room={share} />
		<div class="card problem" role="status">
			<p>{shownToken === token ? SHARE_RESET_MESSAGE : SHARE_UNAVAILABLE_MESSAGE}</p>
			{#if roomHref && shownToken === token}
				<a class="back" href={roomHref}>Back to room</a>
			{/if}
		</div>
	{:else}
		<SavedViewNotice room={share} />
		<ListView room={share} {list} {roomHref} canReset={roomHref !== null} onReset={followReset} />
	{/if}
	{#if share && share.store.status !== 'auth_required'}
		<ConnectionStatus store={share.store} />
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

	/* A link that looks like an outlined button (as on the list page). */
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
