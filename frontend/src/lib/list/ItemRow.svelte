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
	/* Rows are shorter than the usual 44px touch size, so more items fit on
	   the screen; tap areas stay full width where there is room. */
	li {
		--row: 36px;
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-height: var(--row);
		border-bottom: 1px solid var(--border);
	}

	.check {
		display: grid;
		place-items: center;
		width: var(--touch);
		height: var(--row);
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
	/* Buttons are 44px high by default; here they fit the shorter row. */
	.name,
	.qty button,
	.delete {
		min-height: var(--row);
	}

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

	/* A small grey box with − count +, like NiceGUI: compact, so the name
	   keeps its room, but a bit bigger than NiceGUI's for thumbs. */
	.qty {
		display: flex;
		align-items: center;
		flex-shrink: 0;
		/* Extra space on the sides, so a tap meant for the name or a tag does
		   not hit − or +. */
		margin: 0 0.25rem;
		padding: 0 0.125rem;
		border-radius: var(--radius);
		/* The rows sit on the page background, so the box needs another
		   color to show. */
		background: var(--border);
	}

	.qty button {
		width: 20px;
		height: 28px;
		min-width: 0;
		min-height: 0;
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--text);
	}

	/* The icons are 24px; a bit smaller fits the box. */
	.qty :global(svg) {
		width: 18px;
		height: 18px;
	}

	/* One digit wide; 10 and above make the box a little wider. Tabular
	   digits all have the same width, so 1 and 8 take the same space. */
	.count {
		font-variant-numeric: tabular-nums;
		min-width: 1ch;
		padding: 0 0.125rem;
		text-align: center;
		font-size: 0.875rem;
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
		width: 26px;
		height: 26px;
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
