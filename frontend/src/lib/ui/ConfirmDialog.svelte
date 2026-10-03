<!-- A yes/no question, such as "Delete 'Groceries' and its 3 items?". -->
<script lang="ts">
	import Dialog from './Dialog.svelte';

	let {
		question,
		confirmLabel,
		onConfirm,
		onClose
	}: {
		question: string;
		confirmLabel: string;
		onConfirm: () => Promise<void>;
		onClose: () => void;
	} = $props();

	let busy = $state(false);

	async function confirm() {
		busy = true;
		try {
			await onConfirm();
		} finally {
			busy = false;
		}
	}
</script>

<Dialog title={question} {onClose}>
	<div class="actions">
		<button type="button" onclick={onClose}>Cancel</button>
		<button class="danger" type="button" disabled={busy} onclick={confirm}>{confirmLabel}</button>
	</div>
</Dialog>

<style>
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
