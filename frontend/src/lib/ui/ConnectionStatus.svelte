<!--
	A small note at the top of the screen when the connection needs attention:
	"Reconnecting…" while the live stream is down, "Saving…" while changes
	wait for the server. Short waits are normal, so a note only shows when it
	lasts a moment (`CONNECTION_STATUS_DELAY`); it goes as soon as all is well.
	Failed changes are shown as toasts by the page, with the server's message.
-->
<script lang="ts">
	import { connectionStatus, CONNECTION_STATUS_DELAY, type RoomStore } from '#lib/data/index.ts';

	let { store }: { store: RoomStore } = $props();

	const status = $derived(
		connectionStatus({ live: store.live, queued: store.queued, retrying: store.retrying })
	);
	// A boolean `$derived` only changes when the answer changes, so the timer
	// below is not restarted when the text changes (say, Saving → Reconnecting).
	const active = $derived(status !== null);
	let visible = $state(false);

	$effect(() => {
		if (!active) {
			visible = false;
			return;
		}
		const timer = setTimeout(() => (visible = true), CONNECTION_STATUS_DELAY);
		return () => clearTimeout(timer);
	});
</script>

<!-- Always in the page, so screen readers announce the text when it appears. -->
<div class="connection" role="status">
	{#if visible && status}
		<span class="pill {status.kind}">
			<span class="dot" aria-hidden="true"></span>
			{status.text}
		</span>
	{/if}
</div>

<style>
	.connection {
		position: fixed;
		top: calc(0.4rem + env(safe-area-inset-top));
		left: 50%;
		transform: translateX(-50%);
		/* Fits between the back and Options buttons on a phone. */
		max-width: 10rem;
		z-index: 5;
		pointer-events: none;
	}

	.pill {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.3rem 0.7rem;
		border-radius: 999px;
		box-shadow: var(--shadow);
		background: var(--surface);
		color: var(--text-muted);
		font-size: 0.8rem;
		line-height: 1.2;
		white-space: nowrap;
	}

	.offline {
		background: var(--warning);
		color: var(--surface);
	}

	.dot {
		width: 0.5rem;
		height: 0.5rem;
		flex-shrink: 0;
		border-radius: 50%;
		background: currentColor;
		animation: pulse 1.2s ease-in-out infinite;
	}

	@keyframes pulse {
		50% {
			opacity: 0.3;
		}
	}

	/* No blinking for people who asked their device for less motion. */
	@media (prefers-reduced-motion: reduce) {
		.dot {
			animation: none;
		}
	}
</style>
