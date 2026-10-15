<!--
	NiceGUI's "Toggle dark mode" button: switches between light and dark mode
	and remembers the choice in this browser. Pages put it in their top bar;
	the root layout shows one (`corner`) on pages without a bar.
-->
<script lang="ts">
	import Icon from './Icon.svelte';
	import { registerHeaderToggle, theme, toggleThemeWithNotice } from './theme.svelte.ts';

	let { corner = false }: { corner?: boolean } = $props();

	// A toggle in a top bar tells the layout to hide its own.
	$effect(() => (corner ? undefined : registerHeaderToggle()));
</script>

<button
	class="theme"
	type="button"
	aria-label="Toggle dark mode"
	aria-pressed={theme.current === 'dark'}
	title="Toggle light / dark mode"
	onclick={toggleThemeWithNotice}
>
	<Icon name="dark_mode" />
</button>

<style>
	.theme {
		flex-shrink: 0;
		padding: 0;
		display: grid;
		place-items: center;
		border-radius: 50%;
		color: var(--text);
	}
</style>
