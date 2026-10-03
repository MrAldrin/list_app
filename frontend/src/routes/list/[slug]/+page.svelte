<!--
	/app/list/{slug}: the old NiceGUI link shape, without the room. The list page
	needs the room (/app/room/{room}/list/{slug}), so this page sends the
	browser there with the last room it signed in to. If the list is in another
	room, the list page says it is not available.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { lastRoom } from '#lib/data/index.ts';

	let message = $state('');

	$effect(() => {
		const list = page.params.slug ?? '';
		lastRoom()
			.then((slug) => {
				if (slug)
					return goto(resolve('/room/[slug]/list/[list]', { slug, list }), { replaceState: true });
				message = 'Open your room link to continue.';
			})
			.catch(() => {
				message = 'Could not check your last room. Open your room link to continue.';
			});
	});
</script>

<svelte:head>
	<title>List – ListR</title>
</svelte:head>

<main class="page">
	{#if message}
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
