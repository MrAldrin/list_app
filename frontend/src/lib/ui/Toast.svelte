<!--
	Shows the toasts from `toasts.svelte.ts`. It sits once in the root layout,
	and once inside the newest open dialog (`Dialog.svelte`): a modal dialog
	makes everything outside it inert, so toasts outside could not be pressed
	(and a tap on their × would close the dialog). `dialogId` tells which one
	this is; only the one that `toasts.showsToasts()` names draws anything.
	Toasts rise above the bottom bar, suggestions and phone keyboard. When space
	is short, only the newest toasts that fit are shown.
	`aria-live` makes screen readers read new messages out loud.
-->
<script lang="ts">
	import Icon from './Icon.svelte';
	import { toasts } from './toasts.svelte';

	let { dialogId }: { dialogId?: number } = $props();

	const active = $derived(toasts.showsToasts(dialogId));
	let area = $state<HTMLDivElement>();
	let fitSpace = $state<HTMLDivElement>();
	let height = $state(0);
	let shown = $state.raw<number[]>([]);

	// On short screens the suggestion popup scrolls to leave room for the toasts.
	// Suggestions do not open inside dialogs, so only the root stack reports its height.
	$effect(() => {
		if (dialogId !== undefined || !area) return;
		const { style } = document.documentElement;
		style.setProperty('--toast-stack', `${height}px`);
		return () => style.removeProperty('--toast-stack');
	});

	// An open <dialog> sits in the browser's "top layer", above any z-index.
	// As a popover, the toast area joins that layer too; showing it again for
	// each new toast puts it on top of an open dialog.
	$effect(() => {
		const count = toasts.items.length;
		if (!area || typeof area.showPopover !== 'function') return;
		if (area.matches(':popover-open')) area.hidePopover();
		if (count > 0) area.showPopover();
	});

	$effect(() => {
		const items = toasts.items;
		if (!area || !fitSpace || !items.length) return;
		const stack = area;
		const space = fitSpace;
		const rows = stack.querySelectorAll<HTMLDivElement>('.toast');
		const fit = () => {
			let remaining = space.getBoundingClientRect().height;
			const gap = Number.parseFloat(getComputedStyle(stack).rowGap);
			const ids: number[] = [];
			// Keep the newest that fit, without changing the queue or its timers.
			for (let i = rows.length - 1; i >= 0; i--) {
				const rowHeight = rows[i].getBoundingClientRect().height;
				if (rowHeight > 0 && rowHeight <= remaining) {
					ids.push(items[i].id);
					remaining -= rowHeight + gap;
				}
			}
			shown = ids;
		};
		fit();
		let frame = 0;
		const observer = new ResizeObserver(() => {
			// A change in the stack height can resize the popup. Do that next frame.
			cancelAnimationFrame(frame);
			frame = requestAnimationFrame(fit);
		});
		observer.observe(space);
		for (const row of rows) observer.observe(row, { box: 'border-box' });
		return () => {
			observer.disconnect();
			cancelAnimationFrame(frame);
		};
	});
</script>

{#if active}
	<div
		class="toasts"
		bind:this={area}
		bind:offsetHeight={height}
		popover="manual"
		aria-live="polite"
	>
		<div class="fit-space" bind:this={fitSpace} aria-hidden="true"></div>
		{#each toasts.items as toast (toast.id)}
			<div class="toast {toast.kind}" class:does-not-fit={!shown.includes(toast.id)}>
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
		/* The bar height includes the safe area. Without a bar, clear it here. */
		--toast-base: calc(max(var(--bottom-bar, 0px), env(safe-area-inset-bottom)) + var(--toast-gap));
		position: fixed;
		/* Undo the browser's default popover box (centered, border, padding). */
		inset: auto;
		width: auto;
		height: auto;
		max-width: none;
		max-height: none;
		margin: 0;
		border: none;
		padding: 0;
		background: transparent;
		overflow: visible;
		bottom: calc(var(--keyboard, 0px) + var(--toast-base) + var(--bottom-popup, 0px));
		left: max(1rem, env(safe-area-inset-left));
		right: max(1rem, env(safe-area-inset-right));
		display: grid;
		/* One column that may shrink below the text width, so "…" can work. */
		grid-template-columns: minmax(0, 1fr);
		gap: 0.375rem;
		justify-items: center;
		/* Toasts keep their own height, even if Safari makes the area taller. */
		align-content: start;
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

	/* Measure the space above the bar, ignoring the popup. The popup makes
	   room for the shown stack, so including it here would give a feedback loop. */
	.fit-space {
		position: absolute;
		bottom: 0;
		width: 0;
		height: max(
			0px,
			calc(var(--keyboard-view-height, 100dvh) - var(--toast-base) - env(safe-area-inset-top))
		);
		visibility: hidden;
	}

	/* Keep hidden rows measurable at the same width, outside the visible stack. */
	.does-not-fit {
		position: absolute;
		bottom: 0;
		left: 0;
		visibility: hidden;
		pointer-events: none;
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
		min-height: var(--touch);
		color: inherit;
		padding: 0;
	}

	.action {
		padding: 0 0.5rem;
		font-weight: 700;
		text-transform: uppercase;
	}
</style>
