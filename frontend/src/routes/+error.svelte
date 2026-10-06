<!--
	Shown for an address the app does not know (404), and for unexpected errors
	while opening a page. SvelteKit picks this file for any error in the app.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';

	const notFound = $derived(page.status === 404);
</script>

<svelte:head>
	<title>{notFound ? 'Not found' : 'Error'} – ListR</title>
</svelte:head>

<main class="page">
	<div class="card">
		<h1>{notFound ? 'Page not found' : 'Something went wrong'}</h1>
		<p class="muted">
			{notFound
				? 'This address is not part of ListR.'
				: (page.error?.message ?? 'Please try again.')}
		</p>
		<a href={resolve('/')}>Go to the start page</a>
	</div>
</main>

<style>
	.card {
		display: grid;
		gap: var(--gap);
	}

	h1 {
		font-size: 1.3rem;
	}
</style>
