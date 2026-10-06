<!--
	The top bar of the list page: a back link to the room (the app name on a
	share link, as NiceGUI), the list name (cut off with "…" when long), the
	"Options" button (it says "Done" while the options are open) and the list
	menu. The bar stays at the top of the screen while the page scrolls.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from '#lib/ui/Icon.svelte';

	let {
		name,
		roomHref,
		optionsOpen,
		onToggleOptions,
		menu
	}: {
		name: string;
		/** Null on a share link: it gives no way into the room. */
		roomHref: string | null;
		optionsOpen: boolean;
		onToggleOptions: () => void;
		menu?: Snippet;
	} = $props();
</script>

<header class="bar">
	{#if roomHref}
		<a class="back" href={roomHref} aria-label="Back to room"><Icon name="arrow_back" /></a>
	{:else}
		<span class="brand" aria-hidden="true">List<b>R</b></span>
	{/if}
	<h1 title={name}>{name}</h1>
	<div class="end">
		<button type="button" aria-expanded={optionsOpen} onclick={onToggleOptions}>
			{optionsOpen ? 'Done' : 'Options'}
		</button>
		{@render menu?.()}
	</div>
</header>

<style>
	/* `sticky` keeps the bar at the top of the screen once the page scrolls
	   past it. It must be a direct child of the page to stay stuck the whole
	   way down. */
	.bar {
		position: sticky;
		top: 0;
		z-index: 10;
		height: var(--touch);
		background: var(--bg);
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	/* A link styled like a round icon button, with a large touch area. */
	.back {
		flex-shrink: 0;
		display: grid;
		place-items: center;
		width: var(--touch);
		height: var(--touch);
		border-radius: 50%;
		color: var(--text);
	}

	.brand {
		font-size: 1.2rem;
		font-weight: 700;
	}

	.brand b {
		color: var(--primary);
		font-weight: 900;
	}

	.end {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.end > button {
		color: var(--primary);
		font-weight: 600;
	}

	h1 {
		flex: 1;
		min-width: 0;
		margin: 0;
		font-size: 1.25rem;
		/* Long names end with "…" instead of taking more lines. */
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
