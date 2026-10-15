<!--
	The top bar of the room page: app name, room name, the room
	menu (with "Log out" and dark mode). A browser signed in as admin gets a
	back link to the admin page instead of the app name.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import type { RoomHandle } from '#lib/data/index.ts';
	import Brand from '#lib/ui/Brand.svelte';
	import BackLink from '#lib/ui/BackLink.svelte';
	import RoomMenu from './RoomMenu.svelte';

	let {
		room,
		backToAdmin = false,
		onLogout
	}: { room: RoomHandle; backToAdmin?: boolean; onLogout: () => void } = $props();
</script>

<header>
	{#if backToAdmin}
		<BackLink href={resolve('/admin')} label="Back to admin" icon />
	{:else}
		<Brand />
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
