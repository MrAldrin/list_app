<!--
	One item: a checkbox, the name (tap to edit), a note icon when it has a
	description, the date ("18 Oct") when it has one, "×2" for a quantity of
	2 or more, the quantity stepper (when
	"Show quantities" is on; it replaces "×2"), a letter
	button per list tag (filled when the item has the tag) and, in Options
	mode, a delete button. Checkbox, stepper and tags change at once; the data
	layer sends the change in the background.
-->
<script lang="ts">
	import type { Item } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import UnsentMark from '#lib/ui/UnsentMark.svelte';
	import { formatItemDate, quantityBadge } from './items';
	import { tagColor, tagLetters } from './tags';

	let {
		item,
		showQuantity,
		showDelete,
		canEdit,
		listTags,
		unsent = false,
		onToggle,
		onQuantity,
		onTag,
		onOpen,
		onDelete
	}: {
		item: Item;
		showQuantity: boolean;
		showDelete: boolean;
		/** Whether shared-data writes are authorized. */
		canEdit: boolean;
		/** The list's tags, sorted; each gets a letter button. */
		listTags: readonly string[];
		/** A change to this item is not sent yet (a small mark). */
		unsent?: boolean;
		onToggle: (done: boolean) => void;
		onQuantity: (delta: number) => void;
		onTag: (tag: string) => void;
		onOpen: () => void;
		onDelete: () => void;
	} = $props();

	const badge = $derived(quantityBadge(item.quantity, showQuantity));
	/** One letter (or two or three, where tags look alike) per list tag, in the same order. */
	const letters = $derived(tagLetters(listTags));
</script>

<li class:done={item.done}>
	<!-- The label around the checkbox makes the whole 44px square tappable. -->
	<label class="check">
		<input
			type="checkbox"
			checked={item.done}
			aria-label={item.name}
			disabled={!canEdit}
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
		{#if badge}
			<span class="badge">{badge}</span>
		{/if}
		{#if item.date}
			<span class="date">{formatItemDate(item.date)}</span>
		{/if}
	</button>
	{#if unsent}
		<UnsentMark />
	{/if}
	{#if showQuantity}
		<div class="qty" role="group" aria-label="Quantity of {item.name}">
			<button
				type="button"
				aria-label="Less {item.name}"
				disabled={!canEdit || item.quantity <= 1}
				onclick={() => onQuantity(-1)}
			>
				<Icon name="remove" />
			</button>
			<span class="count">{item.quantity}</span>
			<button
				type="button"
				aria-label="More {item.name}"
				disabled={!canEdit}
				onclick={() => onQuantity(1)}
			>
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
					style:--tag={tagColor(tag)}
					type="button"
					aria-label="{tag} tag for {item.name}"
					aria-pressed={on}
					disabled={!canEdit}
					title={tag}
					onclick={() => onTag(tag)}
				>
					<span class="letter">{letters[index]}</span>
				</button>
			{/each}
		</div>
	{/if}
	{#if showDelete}
		<button
			class="delete"
			type="button"
			aria-label="Delete {item.name}"
			disabled={!canEdit}
			onclick={onDelete}
		>
			<Icon name="delete" />
		</button>
	{/if}
</li>

<style>
	/* Rows are as tall as the touch size, so every control in a row is 44px
	   high to tap. */
	li {
		--row: var(--touch);
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-height: var(--row);
		border-bottom: 1px solid var(--border);
	}

	/* app.css makes form labels bold; this label is not a form field. */
	.check {
		font-weight: inherit;
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
	/* Part of the name, so everyone sees the quantity without Options. */
	.badge {
		flex-shrink: 0;
		color: var(--text-muted);
		font-size: 0.875rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	/* Small and muted, after the name: a date is extra, not the main text. */
	.date {
		flex-shrink: 0;
		color: var(--text-muted);
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
	}

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

	/* A 44px tap area; the grey box shows the icon. */
	.qty button {
		width: var(--touch);
		height: var(--row);
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
		flex-shrink: 0;
	}

	/* A 44px tap area per tag, next to each other. */
	.tag {
		width: var(--touch);
		height: var(--row);
		min-width: 0;
		min-height: 0;
		padding: 0;
		border: none;
		display: grid;
		place-items: center;
		color: var(--tag);
	}

	/* The round letter: outlined, filled when the item has the tag. */
	.letter {
		box-sizing: border-box;
		min-width: 26px;
		height: 26px;
		padding: 0 0.1875rem;
		display: grid;
		place-items: center;
		border: 1.5px solid var(--tag);
		border-radius: 13px;
		font-size: 0.8rem;
		font-weight: 700;
	}

	.tag.on .letter {
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
