<!--
	The "Options" panel of the list page. "Sort" comes first, as the option
	changed most often.
	"Sort" and "Show quantities" are personal and saved in this browser; the
	hide-done settings are saved for the list, for everyone.
-->
<script lang="ts">
	import { ITEM_SORTS, type HideDone, type ItemSortChoice } from '#lib/data/index.ts';
	import HideDoneSettings from './HideDoneSettings.svelte';

	// `$bindable` lets the parent write <ListOptions bind:view={…} />.
	let {
		showQuantities = $bindable(),
		sort,
		onSort,
		hideDone,
		canEdit,
		onHideDone
	}: {
		showQuantities: boolean;
		/** The chosen item sort (personal, like "Show quantities"). */
		sort: ItemSortChoice;
		onSort: (choiceId: string) => void;
		hideDone: HideDone;
		canEdit: boolean;
		onHideDone: (changes: Partial<HideDone>) => void;
	} = $props();

	const sortId = $props.id();
</script>

<section class="card" aria-label="Options">
	<label class="switch" for={sortId}>
		<span>Sort</span>
		<select id={sortId} value={sort.id} onchange={(event) => onSort(event.currentTarget.value)}>
			{#each ITEM_SORTS as choice (choice.id)}
				<option value={choice.id}>{choice.label}</option>
			{/each}
		</select>
	</label>
	<label class="switch">
		<span>Show quantities</span>
		<input type="checkbox" role="switch" bind:checked={showQuantities} />
	</label>
	<HideDoneSettings settings={hideDone} disabled={!canEdit} onChange={onHideDone} />
</section>

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
