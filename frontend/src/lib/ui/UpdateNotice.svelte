<!--
	Shown when the server runs another API version than this page expects
	(see lib/data/compat.svelte.ts). Changes are blocked until the page is
	reloaded. The page never reloads by itself, so nothing typed is lost.
-->
<script lang="ts">
	import { compat } from '#lib/data/compat.svelte.ts';
</script>

{#if compat.incompatible}
	<div class="update-notice" role="alert">
		<p>A new version is available. Reload to keep making changes.</p>
		<button type="button" onclick={() => window.location.reload()}>Reload</button>
	</div>
{/if}

<style>
	.update-notice {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 1rem;
		box-sizing: border-box;
		width: calc(100% - 2rem);
		max-width: 32rem;
		margin: 0.5rem auto;
		padding: 0.65rem 0.75rem;
		border-left: 3px solid var(--warning);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
		font-size: 0.9rem;
	}

	p {
		margin: 0;
	}
</style>
