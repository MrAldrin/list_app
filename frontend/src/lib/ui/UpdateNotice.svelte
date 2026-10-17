<!--
	Shown when the server runs another API version than this page expects
	(see lib/data/compat.svelte.ts). Changes are blocked until the page is
	reloaded. This notice never reloads by itself, so nothing typed is lost.
	Unsent changes kept on the device survive a reload; only changes that live
	in this page alone (no storage) are lost, and the notice says so.
-->
<script lang="ts">
	import { compat } from '#lib/data/compat.svelte.ts';
	import { reloadOntoNewVersion } from '#lib/service-worker.ts';

	// Fetching the new version can take a few seconds; one click is enough.
	let reloading = $state(false);

	function reload() {
		reloading = true;
		void reloadOntoNewVersion();
	}
</script>

{#if compat.incompatible}
	<div class="update-notice" role="alert">
		<p>A new version is available. Reload to keep making changes.</p>
		{#if compat.unsavedWrites > 0}
			<p class="warning">
				{compat.unsavedWrites === 1
					? '1 change is not saved yet. Reloading now will lose it.'
					: `${compat.unsavedWrites} changes are not saved yet. Reloading now will lose them.`}
			</p>
		{:else if compat.waitingWrites > 0}
			<p class="warning">
				{compat.waitingWrites === 1
					? '1 change is saved on this phone and is not sent yet.'
					: `${compat.waitingWrites} changes are saved on this phone and are not sent yet.`}
			</p>
		{/if}
		<button type="button" disabled={reloading} onclick={reload}>
			{reloading ? 'Reloading…' : 'Reload'}
		</button>
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

	.warning {
		flex-basis: 100%;
		order: 1;
		font-weight: 600;
	}
</style>
