<!--
	A link to another page, going back. With `icon`, it is a round arrow button
	(the top bar of the room and list pages); `label` is its name for screen
	readers. Otherwise it is an outlined button, and `label` is its text.
-->
<script lang="ts">
	import Icon from './Icon.svelte';

	let { href, label, icon = false }: { href: string; label: string; icon?: boolean } = $props();
</script>

{#if icon}
	<a class="back-icon" {href} aria-label={label}><Icon name="arrow_back" /></a>
{:else}
	<a class="back-text" {href}>{label}</a>
{/if}

<style>
	/* A link styled like a round icon button, with a large touch area. */
	.back-icon {
		display: grid;
		place-items: center;
		flex-shrink: 0;
		width: var(--touch);
		height: var(--touch);
		border-radius: 50%;
		color: var(--text);
	}

	/* A link that looks like an outlined button. It stays a link because it
	   goes to another page. */
	.back-text {
		display: inline-flex;
		align-items: center;
		min-height: var(--touch);
		padding: 0 1rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		background: var(--surface);
		font-weight: 600;
		text-decoration: none;
	}
</style>
