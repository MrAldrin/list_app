<!--
	Shows the toasts from `toasts.svelte.ts`. It sits once in the root layout,
	and once inside the newest open dialog (`Dialog.svelte`): a modal dialog
	makes everything outside it inert, so toasts outside could not be pressed
	(and a tap on their × would close the dialog). `dialogId` tells which one
	this is; only the one that `toasts.showsToasts()` names draws anything.
	`aria-live` makes screen readers read new messages out loud.
-->
<script lang="ts">
	import Icon from './Icon.svelte';
	import { toasts } from './toasts.svelte';

	let { dialogId }: { dialogId?: number } = $props();

	const active = $derived(toasts.showsToasts(dialogId));
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

	// The iPhone keyboard covers the bottom of the screen but does not shrink
	// the page. The visual viewport is the part still visible, so its height
	// tells how far to lift the toasts to keep them above the keyboard.
	$effect(() => {
		const viewport = window.visualViewport;
		if (!area || !viewport) return;
		const target = area;
		const update = () => {
			const covered = window.innerHeight - viewport.height - viewport.offsetTop;
			target.style.setProperty('--keyboard', `${Math.max(0, covered)}px`);
		};
		update();
		viewport.addEventListener('resize', update);
		viewport.addEventListener('scroll', update);
		return () => {
			viewport.removeEventListener('resize', update);
			viewport.removeEventListener('scroll', update);
		};
	});
</script>

{#if active}
	<div class="toasts" bind:this={area} popover="manual" aria-live="polite">
		{#each toasts.items as toast (toast.id)}
			<div class="toast {toast.kind}">
				<span>{toast.message}</span>
				{#if toast.action}
					<button
						class="action"
						type="button"
						disabled={toast.action.disabled?.() ?? false}
						onclick={() => toasts.act(toast.id)}
					>
						{toast.action.label}
					</button>
				{/if}
				<button type="button" aria-label="Dismiss" onclick={() => toasts.dismiss(toast.id)}>
					<Icon name="close" />
				</button>
			</div>
		{/each}
	</div>
{/if}

<style>
	.toasts {
		position: fixed;
		/* Undo the browser's default popover box (centered, border, padding). */
		inset: auto;
		top: auto;
		width: auto;
		height: auto;
		max-width: none;
		max-height: none;
		margin: 0;
		border: none;
		padding: 0;
		background: transparent;
		overflow: visible;
		/* Above the keyboard when it is open (`--keyboard`, set above), and
		   clear of the iPhone home bar (`env(safe-area-inset-bottom)`). */
		bottom: calc(0.5rem + var(--keyboard, 0px) + env(safe-area-inset-bottom));
		left: 1rem;
		right: 1rem;
		display: grid;
		/* One column that may shrink below the text width, so "…" can work. */
		grid-template-columns: minmax(0, 1fr);
		gap: 0.375rem;
		justify-items: center;
		/* Toasts keep their own height, even if Safari makes the area taller. */
		align-content: end;
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
		padding-left: 0.75rem;
		font-size: 0.875rem;
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		background: var(--text);
		color: var(--bg);
		pointer-events: auto;
	}

	/* Long messages end in "…" instead of growing taller. */
	.toast span {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
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
		/* A bit under the usual touch height, so stacked toasts leave the add
		   field visible. */
		min-height: 2rem;
		color: inherit;
		padding: 0;
	}

	.action {
		padding: 0 0.5rem;
		font-weight: 700;
		text-transform: uppercase;
	}
</style>
