<!--
	/list/{slug}: the old NiceGUI link shape, without the room. The list page
	needs the room (/room/{room}/list/{slug}), so this page sends the
	browser there with the last room it signed in to. If the list is in another
	room, the list page says it is not available.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { lastRoom, NetworkError } from '#lib/data/index.ts';
	import LoadError from '#lib/ui/LoadError.svelte';

	let message = $state('');
	let failed = $state(false);

	async function go(list: string) {
		try {
			const slug = await lastRoom();
			if (slug) {
				return goto(resolve('/room/[slug]/list/[list]', { slug, list }), { replaceState: true });
			}
			failed = false;
			message = 'Connect to open this saved list, or open your room link.';
		} catch (error) {
			failed = true;
			// Only "no connection" gets the connect wording; a server error says so.
			message =
				error instanceof NetworkError
					? 'Connect to open this saved list, or retry when the server is available.'
					: 'Could not open this list. Please try again.';
		}
	}

	$effect(() => {
		void go(page.params.slug ?? '');
	});
</script>

<svelte:head>
	<title>List – ListR</title>
</svelte:head>

<main class="page">
	{#if failed}
		<LoadError title={message} onRetry={() => go(page.params.slug ?? '')} />
		<a href={resolve('/')}>Open a room</a>
	{:else if message}
		<div class="card">
			<p>{message}</p>
			<a href={resolve('/')}>Open a room</a>
		</div>
	{:else}
		<p class="muted">Loading…</p>
	{/if}
</main>

<style>
	.card {
		display: grid;
		gap: var(--gap);
	}
</style>
