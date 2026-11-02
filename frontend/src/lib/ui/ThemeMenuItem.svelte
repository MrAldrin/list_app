<!--
	The dark mode switch and the color theme picker as entries of a ⋮ menu
	(room and list menus). The switch does what
	`ThemeToggle` does and counts as a top-bar toggle, so the layout does not
	add its own button above the page. The menu closes after a tap or a choice.
-->
<script lang="ts">
	import { PALETTES } from './theme';
	import {
		choosePalette,
		registerHeaderToggle,
		theme,
		toggleThemeWithNotice
	} from './theme.svelte.ts';

	let { close }: { close: () => void } = $props();

	$effect(() => registerHeaderToggle());

	function toggle() {
		close();
		toggleThemeWithNotice();
	}

	function pick(event: Event) {
		close();
		choosePalette((event.currentTarget as HTMLSelectElement).value);
	}
</script>

<button type="button" aria-pressed={theme.current === 'dark'} onclick={toggle}>Dark mode</button>
<label class="palette">
	Colors
	<select value={theme.palette} onchange={pick}>
		{#each PALETTES as palette (palette.id)}
			<option value={palette.id}>{palette.name}</option>
		{/each}
	</select>
</label>

<style>
	.palette {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		min-height: var(--touch);
		padding: 0 1rem;
		font-weight: normal;
	}

	select {
		min-height: 36px;
		border: 1px solid var(--control-border);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
	}
</style>
