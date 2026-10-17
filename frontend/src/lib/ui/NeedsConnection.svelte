<!--
	"Needs a connection" under controls that do not work offline. Phones have no
	hover, so the title alone is not enough. Buttons point here with
	`aria-describedby` (the same id).
-->
<script lang="ts">
	let { id, show = true }: { id: string; show?: boolean } = $props();
</script>

{#if show}
	<p {id} class="hint">Needs a connection</p>
{/if}

<style>
	.hint {
		margin: 0.25rem 0.5rem 0.5rem;
		color: var(--text-muted);
		font-size: 0.8rem;
		line-height: 1.3;
	}
</style>
