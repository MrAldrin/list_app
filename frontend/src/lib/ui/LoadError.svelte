<!--
	A problem with loading, with a Retry button: for example "Could not load
	this room." with "No connection to the server." below it. The button shows
	"Retrying…" until the retry is done.
-->
<script lang="ts">
	let {
		title,
		detail = null,
		onRetry
	}: { title: string; detail?: string | null; onRetry: () => Promise<unknown> } = $props();

	let busy = $state(false);

	async function retry() {
		busy = true;
		try {
			await onRetry();
		} finally {
			busy = false;
		}
	}
</script>

<div class="card problem" role="status">
	<p>{title}</p>
	{#if detail}
		<p class="muted">{detail}</p>
	{/if}
	<button class="outline" type="button" disabled={busy} onclick={retry}>
		{busy ? 'Retrying…' : 'Retry'}
	</button>
</div>

<style>
	.problem {
		display: grid;
		gap: var(--gap);
		justify-items: start;
		margin-bottom: 1rem;
	}
</style>
