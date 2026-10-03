<!--
	The top of the list page: a back link to the room, the "Options" button
	(it says "Done" while the options are open) and the list name.
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

<header>
	<div class="bar">
		<a class="back" href={roomHref} aria-label="Back to room"><Icon name="arrow_back" /></a>
		<button type="button" aria-expanded={optionsOpen} onclick={onToggleOptions}>
			{optionsOpen ? 'Done' : 'Options'}
		</button>
	</div>
	<h1>{name}</h1>
</header>

<style>
	header {
		display: grid;
		gap: 0.25rem;
		margin-bottom: 0.5rem;
	}

	.bar {
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
		font-size: 1.5rem;
		overflow-wrap: anywhere;
	}
</style>
