<!--
	Shows the toasts from `toasts.svelte.ts`. It sits once in the root layout.
	`aria-live` makes screen readers read new messages out loud.
-->
<script lang="ts">
	import Icon from './Icon.svelte';
	import { toasts } from './toasts.svelte';

	let area = $state<HTMLDivElement>();

	// An open <dialog> sits in the browser's "top layer", above any z-index.
	// As a popover, the toast area joins that layer too; showing it again for
	// each new toast puts it on top of an open dialog.
	$effect(() => {
		const count = toasts.items.length;
		if (!area || typeof area.showPopover !== 'function') return;
		if (area.matches(':popover-open')) area.hidePopover();
		if (count > 0) area.showPopover();
	});
</script>

<div class="toasts" bind:this={area} popover="manual" aria-live="polite">
	{#each toasts.items as toast (toast.id)}
		<div class="toast {toast.kind}">
			<span>{toast.message}</span>
			{#if toast.action}
				<button class="action" type="button" onclick={() => toasts.act(toast.id)}>
					{toast.action.label}
				</button>
			{/if}
			<button type="button" aria-label="Dismiss" onclick={() => toasts.dismiss(toast.id)}>
				<Icon name="close" />
			</button>
		</div>
	{/each}
</div>

<style>
	.toasts {
		position: fixed;
		/* Undo the browser's default popover box (centered, border, padding). */
		inset: auto;
		margin: 0;
		border: none;
		padding: 0;
		background: transparent;
		overflow: visible;
		/* `env(safe-area-inset-bottom)` keeps clear of the iPhone home bar. */
		bottom: calc(1rem + env(safe-area-inset-bottom));
		left: 1rem;
		right: 1rem;
		display: grid;
		gap: 0.5rem;
		justify-items: center;
		/* Clicks pass through the empty area to the page below. */
		pointer-events: none;
		z-index: 10;
	}

	.toast {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		max-width: 30rem;
		width: 100%;
		padding-left: 1rem;
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		background: var(--text);
		color: var(--bg);
		pointer-events: auto;
	}

	.toast span {
		flex: 1;
	}

	.success {
		background: var(--success);
		color: var(--surface);
	}

	.warning {
		background: var(--warning);
		color: var(--surface);
	}

	.danger {
		background: var(--danger);
		color: var(--danger-text);
	}

	button {
		color: inherit;
		padding: 0;
	}

	.action {
		padding: 0 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
	}
</style>
