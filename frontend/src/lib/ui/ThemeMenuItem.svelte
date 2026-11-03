<!--
	The theme entries of a ⋮ menu (room and list menus): "Dark mode", a quick
	switch that closes the menu, and "Appearance", which opens the color theme
	dialog (shown by the root layout). They count as a top-bar toggle, so the
	layout does not add its own theme button above the page.
-->
<script lang="ts">
	import { registerHeaderToggle, theme, toggleThemeWithNotice } from './theme.svelte.ts';

	let { close }: { close: () => void } = $props();
	$effect(() => registerHeaderToggle());

	function toggle() {
		close();
		toggleThemeWithNotice();
	}
</script>

<button type="button" aria-pressed={theme.current === 'dark'} onclick={toggle}>Dark mode</button>
<button
	type="button"
	aria-haspopup="dialog"
	onclick={() => {
		close();
		theme.appearanceOpen = true;
	}}>Appearance</button
>
