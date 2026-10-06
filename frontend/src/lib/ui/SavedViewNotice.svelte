<script lang="ts">
	import type { RoomHandle } from '#lib/data/index.ts';

	let { room }: { room: RoomHandle } = $props();

	const refreshedAt = $derived.by(() => {
		const savedAt = room.store.savedAt;
		if (!savedAt) return null;
		const date = new Date(savedAt);
		return Number.isNaN(date.valueOf()) ? null : date.toLocaleString();
	});
</script>

{#if room.store.readOnly && room.store.unconfirmedView && room.store.savedAt}
	<p class="saved-notice" role="status">
		Saved view — may be out of date.{#if refreshedAt}
			Last refreshed {refreshedAt}.{/if}
	</p>
{/if}
{#if room.store.snapshotWarning}
	<p class="storage-notice" role="status">{room.store.snapshotWarning}</p>
{/if}

<style>
	p {
		margin: 0 0 0.75rem;
		padding: 0.65rem 0.75rem;
		border-left: 3px solid var(--warning);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
		font-size: 0.9rem;
	}

	.storage-notice {
		color: var(--warning);
	}
</style>
