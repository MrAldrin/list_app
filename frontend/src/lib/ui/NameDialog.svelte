<!--
	A dialog with one text field, Cancel and Save. Enter in the field saves.
	Used for "New List" and for renaming a list.
-->
<script lang="ts">
	import { untrack } from 'svelte';
	import Dialog from './Dialog.svelte';

	let {
		title,
		label,
		initial = '',
		onSave,
		onClose
	}: {
		title: string;
		label: string;
		initial?: string;
		/** Saves the name. The parent closes the dialog if it worked. */
		onSave: (name: string) => Promise<void>;
		onClose: () => void;
	} = $props();

	const inputId = $props.id();
	// `untrack`: start with the first value only; later changes of `initial`
	// (for example a live rename by someone else) do not overwrite typing.
	let name = $state(untrack(() => initial));
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		try {
			await onSave(name);
		} finally {
			busy = false;
		}
	}
</script>

<Dialog {title} {onClose}>
	<form onsubmit={submit} novalidate>
		<label for={inputId}>{label}</label>
		<input id={inputId} bind:value={name} autocomplete="off" enterkeyhint="done" />
		<div class="actions">
			<button type="button" onclick={onClose}>Cancel</button>
			<button class="primary" type="submit" disabled={busy}>Save</button>
		</div>
	</form>
</Dialog>

<style>
	form {
		display: grid;
		gap: var(--gap);
	}

	label {
		font-weight: 600;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
