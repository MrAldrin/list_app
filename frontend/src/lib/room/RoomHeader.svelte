<!--
	The top bar of the room page: app name, room name (a button that opens the
	room switcher), the room menu (with "Log out" and dark mode). A browser
	signed in as admin gets a back link to the admin page instead of the app
	name.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import type { RoomHandle } from '#lib/data/index.ts';
	import Brand from '#lib/ui/Brand.svelte';
	import BackLink from '#lib/ui/BackLink.svelte';
	import RoomMenu from './RoomMenu.svelte';
	import RoomSwitcher from './RoomSwitcher.svelte';

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
	<RoomSwitcher {room} />
	<RoomMenu {room} {backToAdmin} {onLogout} />
</header>

<style>
	header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
</style>
