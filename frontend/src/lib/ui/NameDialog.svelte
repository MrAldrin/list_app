<!--
	A dialog with one text field, Cancel and Save. Enter in the field saves.
	Used for "New List" and for renaming a list.
-->
<script lang="ts">
	import { MAX_NAME_LENGTH } from '#lib/ui/field-limits.ts';
	import { untrack } from 'svelte';
	import FormDialog from './FormDialog.svelte';

	let {
		title,
		label,
		initial = '',
		onSave,
		onClose,
		saveDisabled = false
	}: {
		title: string;
		label: string;
		initial?: string;
		/** Saves the name. The parent closes the dialog if it worked. */
		onSave: (name: string) => Promise<void>;
		onClose: () => void;
		saveDisabled?: boolean;
	} = $props();

	const inputId = $props.id();
	// `untrack`: start with the first value only; later changes of `initial`
	// (for example a live rename by someone else) do not overwrite typing.
	let name = $state(untrack(() => initial));
</script>

<FormDialog
	{title}
	submitLabel="Save"
	submitDisabled={saveDisabled}
	onSubmit={() => onSave(name)}
	{onClose}
>
	<label for={inputId}>{label}</label>
	<input
		id={inputId}
		bind:value={name}
		maxlength={MAX_NAME_LENGTH}
		autocomplete="off"
		enterkeyhint="done"
	/>
</FormDialog>
