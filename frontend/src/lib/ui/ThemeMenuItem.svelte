<!--
	The dark mode switch as an entry of a ⋮ menu (room and list menus). It does what
	`ThemeToggle` does and counts as a top-bar toggle, so the layout does not
	add its own button above the page. The menu closes after a tap.
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
