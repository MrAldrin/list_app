<!--
	The top of the list page: a back link to the room, the "Options" button
	(it says "Done" while the options are open) and the list name. The bar
	stays at the top of the screen while the page scrolls; the name does not.
-->
<script lang="ts">
	import Icon from '#lib/ui/Icon.svelte';

	let {
		name,
		roomHref,
		optionsOpen,
		onToggleOptions
	}: { name: string; roomHref: string; optionsOpen: boolean; onToggleOptions: () => void } =
		$props();
</script>

<header class="bar">
	<a class="back" href={roomHref} aria-label="Back to room"><Icon name="arrow_back" /></a>
	<button type="button" aria-expanded={optionsOpen} onclick={onToggleOptions}>
		{optionsOpen ? 'Done' : 'Options'}
	</button>
</header>
<h1>{name}</h1>

<style>
	/* `sticky` keeps the bar at the top of the screen once the page scrolls
	   past it. It must be a direct child of the page to stay stuck the whole
	   way down, so the name is a separate element below it. */
	.bar {
		position: sticky;
		top: 0;
		z-index: 10;
		height: var(--touch);
		background: var(--bg);
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	/* A link styled like a round icon button, with a large touch area. */
	.back {
		display: grid;
		place-items: center;
		width: var(--touch);
		height: var(--touch);
		border-radius: 50%;
		color: var(--text);
	}

	.bar button {
		color: var(--primary);
		font-weight: 600;
	}

	h1 {
		margin: 0.25rem 0 0.5rem;
		font-size: 1.5rem;
		/* Long names end with "…" instead of taking more lines. */
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
