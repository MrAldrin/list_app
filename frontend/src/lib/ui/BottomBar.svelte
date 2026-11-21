<!--
	A bar fixed to the bottom of the screen, within thumb reach on a phone. The
	list page puts "Add or Search" here; the room page puts "Add New List" here.
	An empty spacer of the same height stays in the page, so the last rows can
	scroll out from under the bar. The bar rises above the phone keyboard, but
	stays in place during overscroll. Toasts use the bar's measured height to
	stay above it.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	/** The full bar height, including its border and safe-area padding. */
	let height = $state(0);

	$effect(() => {
		const { style } = document.documentElement;
		style.setProperty('--bottom-bar', `${height}px`);
		return () => style.removeProperty('--bottom-bar');
	});
</script>

<div class="spacer" style:height="{height}px" aria-hidden="true"></div>
<div class="bottom-bar" bind:offsetHeight={height}>
	<div class="inner">
		{@render children()}
	</div>
</div>

<style>
	.bottom-bar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: var(--keyboard, 0px);
		/* Above the items; below the connection pill (20) and dialogs. */
		z-index: 10;
		background: var(--bg);
		border-top: 1px solid var(--border);
		/* Keep the controls clear of the home bar and rounded corners. */
		padding: 0 calc(1rem + env(safe-area-inset-right)) max(0.75rem, env(safe-area-inset-bottom))
			calc(1rem + env(safe-area-inset-left));
	}

	/* The same width as the page column (`.page` in app.css). */
	.inner {
		position: relative;
		max-width: 32rem;
		margin: 0 auto;
	}
</style>
