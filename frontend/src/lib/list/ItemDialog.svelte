<!--
	"Edit Item": name, description and quantity, saved together (or not at all).
	Enter in the name field saves. The delete button deletes the item (with undo).
	It starts with the item as it was when the dialog opened; the save sends
	that version as `base_seq`.
-->
<script lang="ts">
	import { untrack } from 'svelte';
	import type { Item } from '#lib/data/index.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import { stepQuantity } from './items';

	let {
		item,
		onSave,
		onDelete,
		onClose
	}: {
		item: Item;
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
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		try {
			await onSave({ name, description, quantity });
		} finally {
			busy = false;
		}
	}
</script>

<Dialog title="Edit Item" {onClose}>
	<form onsubmit={submit} novalidate>
		<label for={nameId}>Item Name</label>
		<input id={nameId} bind:value={name} autocomplete="off" enterkeyhint="done" />
		<label for={descriptionId}>Description / Notes</label>
		<textarea id={descriptionId} bind:value={description} rows="3"></textarea>
		<div class="quantity">
			<span id="{nameId}-quantity">Quantity</span>
			<div class="stepper" role="group" aria-labelledby="{nameId}-quantity">
				<button
					type="button"
					aria-label="Less"
					disabled={quantity <= 1}
					onclick={() => (quantity = stepQuantity(quantity, -1))}
				>
					<Icon name="remove" />
				</button>
				<output aria-live="polite">{quantity}</output>
				<button
					type="button"
					aria-label="More"
					onclick={() => (quantity = stepQuantity(quantity, 1))}
				>
					<Icon name="add" />
				</button>
			</div>
		</div>
		<div class="actions">
			<button class="delete" type="button" aria-label="Delete Item" onclick={onDelete}>
				<Icon name="delete" />
			</button>
			<span class="spacer"></span>
			<button type="button" onclick={onClose}>Cancel</button>
			<button class="primary" type="submit" disabled={busy}>Save</button>
		</div>
	</form>
</Dialog>

<style>
	form {
		display: grid;
		gap: 0.5rem;
	}

	label {
		font-weight: 600;
	}

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

	.actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.5rem;
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
