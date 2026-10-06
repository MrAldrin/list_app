<!-- A yes/no question, such as "Delete 'Groceries' and its 3 items?". -->
<script lang="ts">
	import Dialog from './Dialog.svelte';

	let {
		question,
		detail,
		confirmLabel,
		onConfirm,
		onClose,
		confirmDisabled = false
	}: {
		question: string;
		/** A line under the question, such as what happens next. */
		detail?: string;
		confirmLabel: string;
		onConfirm: () => Promise<void>;
		onClose: () => void;
		confirmDisabled?: boolean;
	} = $props();

	let busy = $state(false);

	async function confirm() {
		if (busy || confirmDisabled) return;
		busy = true;
		try {
			await onConfirm();
		} finally {
			busy = false;
		}
	}
</script>

<Dialog title={question} {onClose}>
	{#if detail}
		<p class="detail">{detail}</p>
	{/if}
	<div class="actions">
		<button type="button" onclick={onClose}>Cancel</button>
		<button class="danger" type="button" disabled={busy || confirmDisabled} onclick={confirm}
			>{confirmLabel}</button
		>
	</div>
</Dialog>

<style>
	.detail {
		margin-bottom: 0.75rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
