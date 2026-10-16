<script lang="ts">
	import {
		offlineNoticeText,
		SAVED_VIEW_NOTICE_DELAY,
		waitingChangesText,
		type RoomHandle
	} from '#lib/data/index.ts';

	let { room }: { room: RoomHandle } = $props();

	const text = offlineNoticeText();
	/** Stored changes: the ones this device keeps, sent when the connection is back. */
	const waiting = $derived(waitingChangesText(room.waitingCount));

	// A failed read or a lost live connection means offline now. A saved view
	// that only waits for its first answer gets a moment first (see the delay).
	const shows = $derived(room.store.showsOfflineNotice);
	const known = $derived(room.store.error !== null || room.store.live === 'reconnecting');
	let waited = $state(false);

	$effect(() => {
		if (!shows) {
			waited = false;
			return;
		}
		const timer = setTimeout(() => (waited = true), SAVED_VIEW_NOTICE_DELAY);
		return () => clearTimeout(timer);
	});
</script>

{#if shows && (known || waited)}
	<p class="saved-notice" role="status">
		{text}
		{#if waiting}<br />{waiting}{/if}
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
