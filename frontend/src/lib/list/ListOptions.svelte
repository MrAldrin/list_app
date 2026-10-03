<!--
	The "Options" panel of the list page. These switches only change what this
	page shows; nothing is saved (as in NiceGUI).
-->
<script lang="ts">
	import type { QuantityView } from './items';

	// `$bindable` lets the parent write <ListOptions bind:view={…} />.
	let { view = $bindable() }: { view: QuantityView } = $props();
</script>

<section class="card" aria-label="Options">
	<label class="switch">
		<span>Show quantities</span>
		<input type="checkbox" role="switch" bind:checked={view.showQuantities} />
	</label>
	{#if view.showQuantities}
		<label class="switch sub">
			<span>Only show minimum 2</span>
			<input type="checkbox" role="switch" bind:checked={view.onlyAboveOne} />
		</label>
	{/if}
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

	.sub {
		padding-left: 0.75rem;
		border-top: 1px solid var(--border);
		color: var(--text-muted);
	}

	input {
		width: 1.4rem;
		height: 1.4rem;
		min-height: 0;
		margin: 0;
		padding: 0;
		accent-color: var(--primary);
		cursor: pointer;
	}
</style>
