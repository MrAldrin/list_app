<!--
	A dialog with a form: the fields, then the actions row (Cancel and a submit
	button). While `onSubmit` runs, the submit button is disabled and another
	submit is ignored. `onSubmit` decides the outcome itself (toasts, closing);
	it can throw, and the busy state still ends.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import Dialog from './Dialog.svelte';

	let {
		title,
		submitLabel,
		danger = false,
		submitDisabled = false,
		focusBox = false,
		onSubmit,
		onClose,
		leading,
		children
	}: {
		title: string;
		submitLabel: string;
		/** A red submit button, for a change that cannot be undone. */
		danger?: boolean;
		/** Blocks submit and disables the button, for example in a read-only room. */
		submitDisabled?: boolean;
		/** Focus the dialog, not its first field (see Dialog). */
		focusBox?: boolean;
		onSubmit: () => Promise<void>;
		onClose: () => void;
		/** Optional buttons at the start of the actions row, such as Delete. */
		leading?: Snippet;
		/** The fields. */
		children: Snippet;
	} = $props();

	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy || submitDisabled) return;
		busy = true;
		try {
			await onSubmit();
		} finally {
			busy = false;
		}
	}
</script>

<Dialog {title} {onClose} {focusBox}>
	<form class:with-leading={leading} onsubmit={submit} novalidate>
		{@render children()}
		<div class="actions">
			{#if leading}{@render leading()}{/if}
			<button type="button" onclick={onClose}>Cancel</button>
			<button class={danger ? 'danger' : 'primary'} type="submit" disabled={busy || submitDisabled}
				>{submitLabel}</button
			>
		</div>
	</form>
</Dialog>

<style>
	/* With leading buttons (the item editor): a tighter form, and the buttons
	   spread over the row, since the leading spacer pushes them apart. */
	form.with-leading {
		gap: 0.5rem;
	}

	.with-leading .actions {
		align-items: center;
		justify-content: normal;
		margin-top: 0.5rem;
	}
</style>
