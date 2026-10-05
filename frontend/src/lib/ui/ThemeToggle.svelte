<!--
	NiceGUI's "Toggle dark mode" button: switches between light and dark mode
	and remembers the choice in this browser. Pages put it in their top bar;
	the root layout shows one (`corner`) on pages without a bar.
-->
<script lang="ts">
	import Icon from './Icon.svelte';
	import { registerHeaderToggle, theme, toggleTheme } from './theme.svelte.ts';
	import { toasts } from './toasts.svelte.ts';

	let { corner = false }: { corner?: boolean } = $props();

	// A toggle in a top bar tells the layout to hide its own.
	$effect(() => (corner ? undefined : registerHeaderToggle()));

	function toggle() {
		// NiceGUI's warning; the page still switches until it is reloaded.
		if (!toggleTheme()) toasts.show('Theme could not be saved on this device', 'warning');
	}
</script>

<button
	class="theme"
	type="button"
	aria-label="Toggle dark mode"
	aria-pressed={theme.current === 'dark'}
	title="Toggle light / dark mode"
	onclick={toggle}
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
