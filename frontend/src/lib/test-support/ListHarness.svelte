<!-- Use the same store-to-list projection as a route, with no mocked mutations. -->
<script lang="ts">
	import type { RoomHandle } from '#lib/data/index.ts';
	import ListView from '#lib/list/ListView.svelte';
	import Toast from '#lib/ui/Toast.svelte';
	let { room, uid }: { room: RoomHandle; uid: string } = $props();
	const list = $derived(room.store.list(uid));
</script>

{#if list}<ListView {room} {list} roomHref={null} canReset={false} />{/if}
<Toast />
