<script lang="ts">
	import favicon from '#lib/assets/favicon.svg';
	import Toast from '#lib/ui/Toast.svelte';
	// Importing a CSS file here adds it to every page.
	import '../app.css';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
<!-- In the layout, so toasts stay visible while moving between pages. -->
<Toast />
