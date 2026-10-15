<!--
	"Edit Item": name, description and quantity, saved together (or not at all).
	Enter in the name field saves. The delete button deletes the item (with undo).
	It starts with the item as it was when the dialog opened; the save sends
	that version as `base_seq`.
-->
<script lang="ts">
	import { MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH } from '#lib/ui/field-limits.ts';
	import { untrack } from 'svelte';
	import type { Item } from '#lib/data/index.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import { stepQuantity } from './items';

	let {
		item,
		canWrite,
		onSave,
		onDelete,
		onClose
	}: {
		item: Item;
		/** Whether shared-data writes are authorized. */
		canWrite: boolean;
		/** Saves the fields. The parent closes the dialog if it worked. */
		onSave: (changes: { name: string; description: string; quantity: number }) => Promise<void>;
		onDelete: () => void;
		onClose: () => void;
	} = $props();

	const nameId = $props.id();
	const descriptionId = `${nameId}-description`;
	// `untrack`: start with the values at opening; live changes by someone
	// else do not overwrite what is being typed.
	let name = $state(untrack(() => item.name));
	let description = $state(untrack(() => item.description));
	let quantity = $state(untrack(() => item.quantity));
</script>

<FormDialog
	title="Edit Item"
	submitLabel="Save"
	submitDisabled={!canWrite}
	focusBox
	onSubmit={() => onSave({ name, description, quantity })}
	{onClose}
>
	<label for={nameId}>Item Name</label>
	<input
		id={nameId}
		bind:value={name}
		maxlength={MAX_NAME_LENGTH}
		autocomplete="off"
		enterkeyhint="done"
	/>
	<label for={descriptionId}>Description / Notes</label>
	<textarea id={descriptionId} bind:value={description} maxlength={MAX_DESCRIPTION_LENGTH} rows="3"
	></textarea>
	<div class="quantity">
		<span id="{nameId}-quantity">Quantity</span>
		<div class="stepper" role="group" aria-labelledby="{nameId}-quantity">
			<button
				type="button"
				aria-label="Less"
				disabled={!canWrite || quantity <= 1}
				onclick={() => (quantity = stepQuantity(quantity, -1))}
			>
				<Icon name="remove" />
			</button>
			<output aria-live="polite">{quantity}</output>
			<button
				type="button"
				aria-label="More"
				disabled={!canWrite}
				onclick={() => (quantity = stepQuantity(quantity, 1))}
			>
				<Icon name="add" />
			</button>
		</div>
	</div>
	{#snippet leading()}
		<button
			class="delete"
			type="button"
			aria-label="Delete Item"
			disabled={!canWrite}
			onclick={onDelete}
		>
			<Icon name="delete" />
		</button>
		<span class="spacer"></span>
	{/snippet}
</FormDialog>

<style>
	.quantity {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-left: 0.75rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		font-weight: 600;
	}

	.stepper {
		display: flex;
		align-items: center;
	}

	.stepper button {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--primary);
	}

	output {
		min-width: 2rem;
		text-align: center;
		font-weight: 700;
	}

	.spacer {
		flex: 1;
	}

	.delete {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--danger);
	}
</style>
