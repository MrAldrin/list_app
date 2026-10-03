<!--
	One item: a checkbox and the name. A checked item is crossed out. The
	checkbox changes at once; the data layer sends the change in the background.
-->
<script lang="ts">
	import type { Item } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';

	let { item, onToggle }: { item: Item; onToggle: (done: boolean) => void } = $props();
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
	<span class="name">{item.name}</span>
	{#if item.description}
		<span class="note" title={item.description}><Icon name="description" /></span>
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

	.name {
		flex: 1;
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.done .name {
		text-decoration: line-through;
		color: var(--text-muted);
	}

	.note {
		color: var(--text-muted);
		transform: scale(0.75);
	}
</style>
