<!--
	Small inline SVG icons (Material Design shapes). They take the text color
	(`currentColor`), so they work in light and dark mode. Buttons with only an
	icon need an `aria-label`, so screen readers can name them.
-->
<script lang="ts">
	const PATHS = {
		add: 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
		edit: 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',
		delete: 'M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z',
		close:
			'M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z'
	};

	let { name }: { name: keyof typeof PATHS } = $props();
</script>

<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" fill="currentColor">
	<path d={PATHS[name]} />
</svg>

<style>
	svg {
		display: block;
		flex-shrink: 0;
	}
</style>
