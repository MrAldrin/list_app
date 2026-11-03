<!--
	The Appearance dialog: the color themes as swatch cards (dark mode is its
	own entry in the ⋮ menu). A tap applies a theme at once and keeps the dialog open, so themes
	can be compared. Opened from the ⋮ menu; shown by the root layout.
-->
<script lang="ts">
	import Dialog from './Dialog.svelte';
	import { PALETTES } from './theme';
	import { choosePalette, theme } from './theme.svelte.ts';

	let { onClose }: { onClose: () => void } = $props();
</script>

<Dialog title="Appearance" {onClose}>
	<fieldset>
		<legend>Color theme</legend>
		{#each PALETTES as palette (palette.id)}
			<label class="palette" class:selected={theme.palette === palette.id}>
				<input
					type="radio"
					name="palette"
					value={palette.id}
					checked={theme.palette === palette.id}
					onchange={() => choosePalette(palette.id)}
				/>
				<span class="name">{palette.name}</span>
				<span class="swatches" aria-hidden="true">
					{#each palette.swatches[theme.current] as color, index (index)}
						<span style:background-color={color}></span>
					{/each}
				</span>
			</label>
		{/each}
	</fieldset>
	<button type="button" onclick={onClose}>Close</button>
</Dialog>

<style>
	fieldset {
		border: 0;
		padding: 0;
		margin: 0 0 0.5rem;
	}
	legend {
		font-weight: 500;
		margin-bottom: 0.25rem;
	}
	/* One row per theme: radio, name, then the swatches at the right edge. */
	.palette {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		min-height: var(--touch);
		margin: 0.25rem 0;
		padding: 0.25rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		cursor: pointer;
	}
	.palette.selected {
		border-color: var(--primary);
		box-shadow: inset 0 0 0 1px var(--primary);
	}
	/* Undo the app-wide text-field style for these radios. */
	.palette input {
		flex: none;
		width: 1.25rem;
		height: 1.25rem;
		min-height: 0;
		margin: 0;
		padding: 0;
		accent-color: var(--primary);
	}
	.name {
		flex: 1;
		min-width: 0;
		text-align: left;
		font-weight: 500;
	}
	.swatches {
		flex: none;
		display: flex;
		border: 1px solid var(--control-border);
		border-radius: 4px;
		overflow: hidden;
	}
	.swatches span {
		width: 1rem;
		height: 1.5rem;
	}
</style>
