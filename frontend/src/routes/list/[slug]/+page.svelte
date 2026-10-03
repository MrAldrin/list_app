<!--
	Placeholder for the list page (/app/list/{slug}); the real page comes in
	step 2.4 of the rewrite plan. It exists so room links already work.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
</script>

<svelte:head>
	<title>List – ListR</title>
</svelte:head>

<main class="page">
	<div class="card">
		<p>The list page comes in a later step.</p>
		<!-- The start page goes back to the last room. -->
		<a href={resolve('/')}>Back to the room</a>
	</div>
</main>

<style>
	.card {
		display: grid;
		gap: var(--gap);
	}
</style>
