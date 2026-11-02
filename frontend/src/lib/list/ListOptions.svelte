<!--
	The "Options" panel of the list page. "Sort by" and its direction come
	first, as the options changed most often.
	"Sort" and "Show quantities" are personal and saved in this browser; the
	hide-done settings are saved for the list, for everyone.
-->
<script lang="ts">
	import {
		ITEM_SORT_KEYS,
		itemSortDirections,
		itemSortFor,
		type HideDone,
		type Item,
		type ItemSortChoice,
		type ItemSortKey,
		type TagMode,
		type TagSettings
	} from '#lib/data/index.ts';
	import HideDoneSettings from './HideDoneSettings.svelte';
	import OptionDialogRow from './OptionDialogRow.svelte';
	import TagsDialog from './TagsDialog.svelte';

	// `$bindable` lets the parent write <ListOptions bind:view={…} />.
	let {
		showQuantities = $bindable(),
		sort,
		onSort,
		hideDone,
		tagSettings,
		tags,
		items,
		canEdit,
		onHideDone,
		onTagSettings,
		onTagColor,
		onAddTag,
		onDeleteTag
	}: {
		showQuantities: boolean;
		/** The chosen item sort (personal, like "Show quantities"). */
		sort: ItemSortChoice;
		onSort: (choice: ItemSortChoice) => void;
		hideDone: HideDone;
		/** The list's tag settings (mode, colors, show on items). */
		tagSettings: TagSettings;
		/** The list's tags, sorted ignoring case. */
		tags: readonly string[];
		/** The list's items, to count those with several tags before a switch to one tag. */
		items: readonly Item[];
		canEdit: boolean;
		onHideDone: (changes: Partial<HideDone>) => void;
		onTagSettings: (changes: {
			mode?: TagMode;
			show_on_items?: boolean;
			only_item_tags?: boolean;
		}) => void;
		onTagColor: (tag: string, index: number) => void;
		/** Adds a tag; true when the field should be cleared. */
		onAddTag: (tag: string) => Promise<boolean>;
		onDeleteTag: (tag: string) => void;
	} = $props();

	const uid = $props.id();
	const sortId = `${uid}-sort`;
	const directionId = `${uid}-direction`;
	let directions = $derived(itemSortDirections(sort.key));
	let tagsOpen = $state(false);
</script>

<section class="card" aria-label="Options">
	<!-- A new key starts in its default direction ("Most first", "Newest first"). -->
	<label class="switch" for={sortId}>
		<span>Sort by</span>
		<select
			id={sortId}
			value={sort.key}
			onchange={(event) => onSort(itemSortFor(event.currentTarget.value as ItemSortKey, false))}
		>
			{#each ITEM_SORT_KEYS as option (option.key)}
				<option value={option.key}>{option.label}</option>
			{/each}
		</select>
	</label>
	<label class="switch" for={directionId}>
		<span>Order</span>
		<select
			id={directionId}
			value={sort.id}
			onchange={(event) =>
				onSort(directions.find((choice) => choice.id === event.currentTarget.value) ?? sort)}
		>
			{#each directions as choice (choice.id)}
				<option value={choice.id}>{choice.direction}</option>
			{/each}
		</select>
	</label>
	<label class="switch">
		<span>Show quantities</span>
		<input type="checkbox" role="switch" bind:checked={showQuantities} />
	</label>
	<HideDoneSettings settings={hideDone} disabled={!canEdit} onChange={onHideDone} />
</section>

<OptionDialogRow label="Tags" open={tagsOpen} onOpen={() => (tagsOpen = true)} />
{#if tagsOpen}
	<TagsDialog
		{tags}
		settings={tagSettings}
		{items}
		{canEdit}
		onSettings={onTagSettings}
		onColor={onTagColor}
		onAdd={onAddTag}
		onDelete={onDeleteTag}
		onClose={() => (tagsOpen = false)}
	/>
{/if}

<style>
	section {
		display: grid;
		gap: 0.25rem;
		padding: 0.25rem 0.75rem;
		margin-bottom: 0.5rem;
	}

	.switch {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		min-height: var(--touch);
		font-weight: 500;
		cursor: pointer;
	}

	.switch select {
		min-height: var(--touch);
		max-width: 60%;
	}
</style>
