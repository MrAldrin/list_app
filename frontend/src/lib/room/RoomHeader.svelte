<!-- The room header stays the same whether or not admin is signed in. -->
<script lang="ts">
	import type { RoomHandle } from '#lib/data/index.ts';
	import Brand from '#lib/ui/Brand.svelte';
	import RoomMenu from './RoomMenu.svelte';
	import RoomSwitcher from './RoomSwitcher.svelte';

	let { room, onLogout }: { room: RoomHandle; onLogout: () => void } = $props();
</script>

<header>
	<Brand />
	<RoomSwitcher {room} />
	<RoomMenu {room} {onLogout} />
</header>

<style>
	header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
</style>
