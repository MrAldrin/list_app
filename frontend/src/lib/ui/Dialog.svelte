<!--
	A modal dialog, built on the browser's own <dialog> element. The browser
	then handles the dark backdrop, keeps keyboard focus inside the dialog and
	closes it with Escape.

	Show it with {#if …}<Dialog …>…</Dialog>{/if}: it opens when it appears, and
	calls `onClose` when the user closes it (Escape). The parent then hides it.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';

	let { title, onClose, children }: { title: string; onClose: () => void; children: Snippet } =
		$props();

	// `$props.id()` gives an id that is unique on the page.
	const titleId = $props.id();
	let dialog = $state<HTMLDialogElement>();

	$effect(() => {
		// `showModal()` (not `show()`) makes the rest of the page inert.
		dialog?.showModal();
	});
</script>

<dialog bind:this={dialog} aria-labelledby={titleId} onclose={onClose}>
	<h2 id={titleId}>{title}</h2>
	<!-- The dialog's content, passed in by the parent between the tags. -->
	{@render children()}
</dialog>

<style>
	dialog {
		width: min(100% - 2rem, 24rem);
		border: none;
		border-radius: var(--radius);
		padding: 1rem;
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow);
	}

	dialog::backdrop {
		background: rgb(0 0 0 / 0.45);
	}

	h2 {
		font-size: 1.15rem;
		margin-bottom: 0.75rem;
		/* Long list names wrap instead of widening the dialog. */
		overflow-wrap: anywhere;
	}
</style>
