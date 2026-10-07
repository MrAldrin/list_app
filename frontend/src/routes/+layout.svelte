<script lang="ts">
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { manifestHref } from '#lib/install/manifest.ts';
	import { registerServiceWorker } from '#lib/service-worker.ts';
	import { endStaleBuildReload } from '#lib/stale-build.ts';
	import ThemeToggle from '#lib/ui/ThemeToggle.svelte';
	import { startTheme, theme } from '#lib/ui/theme.svelte.ts';
	import Toast from '#lib/ui/Toast.svelte';
	import UpdateNotice from '#lib/ui/UpdateNotice.svelte';
	// Importing a CSS file here adds it to every page.
	import '../app.css';

	let { children } = $props();

	// One manifest link for the whole app, changed when the page changes: the
	// room page's icon opens that room, any other page's the start page.
	// `resolve('/')` is the app's base path with a slash: `/`.
	const base = resolve('/').replace(/\/$/, '');
	const manifest = $derived(manifestHref(page.route.id, page.params, base));

	// Light or dark mode for every page; it follows the system while no
	// choice is saved. The returned function stops that when the app closes.
	$effect(() => startTheme());

	onMount(() => {
		// The first page loaded; a failed lazy import after this is SvelteKit's to handle.
		endStaleBuildReload();
		void registerServiceWorker();
	});
</script>

<svelte:head>
	<link rel="manifest" href={manifest} />
</svelte:head>

<!-- NiceGUI has its dark mode button on every page. Pages with a top bar
     show it there; the others get it here, above the page. -->
{#if theme.headerToggles === 0}
	<div class="theme-corner"><ThemeToggle corner /></div>
{/if}
<UpdateNotice />
{@render children()}
<!-- In the layout, so toasts stay visible while moving between pages. -->
<Toast />

<style>
	/* Lined up with the right edge of the page column (`.page` in app.css). */
	.theme-corner {
		display: flex;
		justify-content: flex-end;
		max-width: 32rem;
		margin: 0 auto;
		padding: 0.5rem 1rem 0;
	}
</style>
