<!--
	A bar fixed to the bottom of the screen, within thumb reach on a phone. The
	list page puts "Add or Search" here; the room page puts "Add New List" here.
	An empty spacer of the same height stays in the page, so the last rows can
	scroll out from under the bar. On an iPhone the bar rises above the open
	keyboard (see the effect below). Toasts show at the top of the screen, so
	they never cover the bar.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();

	let bar = $state<HTMLDivElement>();
	/** The bar's height, measured by the browser, for the spacer. */
	let height = $state(0);

	// The iPhone keyboard covers the bottom of the screen but does not shrink
	// the page, so a `bottom: 0` bar would hide behind it. The visual viewport
	// is the part still visible; its size tells how far to lift the bar.
	$effect(() => {
		const viewport = window.visualViewport;
		if (!bar || !viewport) return;
		const target = bar;
		const update = () => {
			const covered = window.innerHeight - viewport.height - viewport.offsetTop;
			target.style.setProperty('--keyboard', `${Math.max(0, covered)}px`);
		};
		update();
		viewport.addEventListener('resize', update);
		viewport.addEventListener('scroll', update);
		return () => {
			viewport.removeEventListener('resize', update);
			viewport.removeEventListener('scroll', update);
		};
	});
</script>

<div class="spacer" style:height="{height}px" aria-hidden="true"></div>
<div class="bottom-bar" bind:this={bar} bind:clientHeight={height}>
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
		/* Clear of the iPhone home bar when the keyboard is closed. */
		padding: 0 1rem env(safe-area-inset-bottom);
	}

	/* The same width as the page column (`.page` in app.css). */
	.inner {
		position: relative;
		max-width: 32rem;
		margin: 0 auto;
	}
</style>
