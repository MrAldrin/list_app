<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { manifestHref } from '#lib/install/manifest.ts';
	import Toast from '#lib/ui/Toast.svelte';
	// Importing a CSS file here adds it to every page.
	import '../app.css';

	let { children } = $props();

	// One manifest link for the whole app, changed when the page changes: the
	// room page's icon opens that room, any other page's the start page.
	// `resolve('/')` is the app's base path with a slash: `/app/` until the switch.
	const base = resolve('/').replace(/\/$/, '');
	const manifest = $derived(manifestHref(page.route.id, page.params, base));
</script>

<svelte:head>
	<link rel="manifest" href={manifest} />
</svelte:head>

{@render children()}
<!-- In the layout, so toasts stay visible while moving between pages. -->
<Toast />
