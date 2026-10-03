<!-- The top of the list page: a back link to the room and the list name. -->
<script lang="ts">
	import Icon from '#lib/ui/Icon.svelte';

	let { name, roomHref }: { name: string; roomHref: string } = $props();
</script>

<header>
	<div class="bar">
		<a class="back" href={roomHref} aria-label="Back to room"><Icon name="arrow_back" /></a>
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

	h1 {
		font-size: 1.5rem;
		overflow-wrap: anywhere;
	}
</style>
