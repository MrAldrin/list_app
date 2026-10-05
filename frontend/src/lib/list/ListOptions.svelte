<!--
	The "Options" panel of the list page. "Show quantities" is personal and
	saved in this browser; the hide-done settings below it are saved for the
	list, for everyone.
-->
<script lang="ts">
	import type { HideDone } from '#lib/data/index.ts';
	import HideDoneSettings from './HideDoneSettings.svelte';

	// `$bindable` lets the parent write <ListOptions bind:view={…} />.
	let {
		showQuantities = $bindable(),
		hideDone,
		onHideDone
	}: {
		showQuantities: boolean;
		hideDone: HideDone;
		onHideDone: (changes: Partial<HideDone>) => void;
	} = $props();
</script>

<section class="card" aria-label="Options">
	<label class="switch">
		<span>Show quantities</span>
		<input type="checkbox" role="switch" bind:checked={showQuantities} />
	</label>
	<HideDoneSettings settings={hideDone} onChange={onHideDone} />
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
		min-height: var(--touch);
		font-weight: 500;
		cursor: pointer;
	}
</style>
