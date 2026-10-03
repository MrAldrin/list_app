<!--
	One item: a checkbox, the name (tap to edit), a note icon when it has a
	description, the quantity stepper (when "Show quantities" is on) and, in
	Options mode, a delete button. Checkbox and stepper change at once; the
	data layer sends the change in the background.
-->
<script lang="ts">
	import type { Item } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';

	let {
		item,
		showQuantity,
		showDelete,
		onToggle,
		onQuantity,
		onOpen,
		onDelete
	}: {
		item: Item;
		showQuantity: boolean;
		showDelete: boolean;
		onToggle: (done: boolean) => void;
		onQuantity: (delta: number) => void;
		onOpen: () => void;
		onDelete: () => void;
	} = $props();
</script>

<li class:done={item.done}>
	<!-- The label around the checkbox makes the whole 44px square tappable. -->
	<label class="check">
		<input
			type="checkbox"
			checked={item.done}
			aria-label={item.name}
			onchange={(event) => onToggle(event.currentTarget.checked)}
		/>
	</label>
	<button class="name" type="button" onclick={onOpen}>
		<span>{item.name}</span>
		{#if item.description}
			<span class="note" title={item.description}>
				<Icon name="description" />
				<span class="visually-hidden">(has notes)</span>
			</span>
		{/if}
	</button>
	{#if showQuantity}
		<div class="qty" role="group" aria-label="Quantity of {item.name}">
			<button
				type="button"
				aria-label="Less {item.name}"
				disabled={item.quantity <= 1}
				onclick={() => onQuantity(-1)}
			>
				<Icon name="remove" />
			</button>
			<span class="count">{item.quantity}</span>
			<button type="button" aria-label="More {item.name}" onclick={() => onQuantity(1)}>
				<Icon name="add" />
			</button>
		</div>
	{/if}
	{#if showDelete}
		<button class="delete" type="button" aria-label="Delete {item.name}" onclick={onDelete}>
			<Icon name="delete" />
		</button>
	{/if}
</li>

<style>
	li {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-height: var(--touch);
		border-bottom: 1px solid var(--border);
	}

	.check {
		display: grid;
		place-items: center;
		width: var(--touch);
		height: var(--touch);
		flex-shrink: 0;
		cursor: pointer;
	}

	.check input {
		width: 1.4rem;
		height: 1.4rem;
		min-height: 0;
		margin: 0;
		padding: 0;
		accent-color: var(--primary);
		cursor: pointer;
	}

	/* The name is a button that fills the row, so it is easy to tap. */
	.name {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0 0.25rem;
		text-align: left;
		overflow-wrap: anywhere;
	}

	.done .name {
		text-decoration: line-through;
		color: var(--text-muted);
	}

	.note {
		display: flex;
		color: var(--text-muted);
		transform: scale(0.75);
	}

	.qty {
		display: flex;
		align-items: center;
		flex-shrink: 0;
		border-radius: var(--radius);
		background: var(--bg);
	}

	.qty button {
		padding: 0;
		display: grid;
		place-items: center;
	}

	.count {
		min-width: 1.5rem;
		text-align: center;
		font-weight: 700;
	}

	.delete {
		padding: 0;
		display: grid;
		place-items: center;
		flex-shrink: 0;
		color: var(--danger);
	}
</style>
