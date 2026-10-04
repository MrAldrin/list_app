<!--
	One item: a checkbox, the name (tap to edit), a note icon when it has a
	description, the quantity stepper (when "Show quantities" is on), a letter
	button per list tag (filled when the item has the tag) and, in Options
	mode, a delete button. Checkbox, stepper and tags change at once; the data
	layer sends the change in the background.
-->
<script lang="ts">
	import type { Item } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import { tagColor, tagLetter } from './tags';

	let {
		item,
		showQuantity,
		showDelete,
		listTags,
		onToggle,
		onQuantity,
		onTag,
		onOpen,
		onDelete
	}: {
		item: Item;
		showQuantity: boolean;
		showDelete: boolean;
		/** The list's tags, sorted; each gets a letter button. */
		listTags: readonly string[];
		onToggle: (done: boolean) => void;
		onQuantity: (delta: number) => void;
		onTag: (tag: string) => void;
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
		<span class="text">{item.name}</span>
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
	{#if listTags.length > 0}
		<div class="tags">
			{#each listTags as tag, index (tag)}
				{@const on = item.tags.includes(tag)}
				<button
					class="tag"
					class:on
					style:--tag={tagColor(index)}
					type="button"
					aria-label="{tag} tag for {item.name}"
					aria-pressed={on}
					title={tag}
					onclick={() => onTag(tag)}
				>
					{tagLetter(tag)}
				</button>
			{/each}
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
	}

	/* Long names stay on one line and end with "…"; the edit dialog shows
	   the full name. */
	.text {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.done .name {
		text-decoration: line-through;
		color: var(--text-muted);
	}

	.note {
		display: flex;
		flex-shrink: 0;
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

	.tags {
		display: flex;
		align-items: center;
		gap: 0.125rem;
		flex-shrink: 0;
	}

	/* A round letter button: outlined, filled when the item has the tag. */
	.tag {
		width: 2rem;
		height: 2rem;
		min-width: 0;
		min-height: 0;
		padding: 0;
		border: 1.5px solid var(--tag);
		border-radius: 50%;
		color: var(--tag);
		font-size: 0.8rem;
		font-weight: 700;
	}

	.tag.on {
		background: var(--tag);
		color: var(--tag-text);
	}

	.delete {
		padding: 0;
		display: grid;
		place-items: center;
		flex-shrink: 0;
		color: var(--danger);
	}
</style>
