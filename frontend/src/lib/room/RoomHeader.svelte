<!--
	The top bar of the room page: app name, room name, the room
	menu (with "Log out" and dark mode). A browser signed in as admin gets a
	back link to the admin page instead of the app name.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import type { RoomHandle } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import RoomMenu from './RoomMenu.svelte';

	let {
		room,
		backToAdmin = false,
		onLogout
	}: { room: RoomHandle; backToAdmin?: boolean; onLogout: () => void } = $props();
</script>

<header>
	{#if backToAdmin}
		<a class="back" href={resolve('/admin')} aria-label="Back to admin"
			><Icon name="arrow_back" /></a
		>
	{:else}
		<span class="brand" aria-hidden="true">List<b>R</b></span>
	{/if}
	<h1>{room.store.room?.name ?? ''}</h1>
	<RoomMenu {room} {backToAdmin} {onLogout} />
</header>

<style>
	header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	/* A link styled like a round icon button, with a large touch area. */
	.back {
		display: grid;
		place-items: center;
		width: var(--touch);
		height: var(--touch);
		flex-shrink: 0;
		border-radius: 50%;
		color: var(--text);
	}

	.brand {
		font-size: 1.2rem;
		font-weight: 700;
	}

	.brand b {
		color: var(--primary);
		font-weight: 900;
	}

	h1 {
		flex: 1;
		min-width: 0;
		font-size: 1.5rem;
		/* Long room names end with "…" instead of breaking the layout. */
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
