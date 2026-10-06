<!--
	A modal dialog, built on the browser's own <dialog> element. The browser
	then handles the dark backdrop, keeps keyboard focus inside the dialog and
	closes it with Escape. A click on the backdrop closes it too, as NiceGUI.

	Show it with {#if …}<Dialog …>…</Dialog>{/if}: it opens when it appears, and
	calls `onClose` when the user closes it (Escape or a click outside). The parent then hides it.
-->
<script lang="ts">
	import { untrack, type Snippet } from 'svelte';
	import Toast from './Toast.svelte';
	import { toasts } from './toasts.svelte.ts';

	let {
		title,
		onClose,
		focusBox = false,
		children
	}: {
		title: string;
		onClose: () => void;
		/** Focus the dialog, not its first field, so a phone keyboard stays closed. */
		focusBox?: boolean;
		children: Snippet;
	} = $props();

	// `$props.id()` gives an id that is unique on the page.
	const titleId = $props.id();
	let dialog = $state<HTMLDialogElement>();
	// While this dialog is open it shows the toasts (see `Toast.svelte`). The
	// id is set once the dialog is open, so the toasts are never shown in a
	// dialog that is not on screen yet.
	let toastId = $state<number>();

	$effect(() => {
		if (!dialog) return;
		const box = dialog;
		// The button that opened the dialog, to give the focus back afterwards.
		const opener = document.activeElement;
		// `showModal()` (not `show()`) makes the rest of the page inert.
		box.showModal();
		if (focusBox) box.focus();
		// `untrack`: the list is read and written here, which must not rerun this effect.
		const id = untrack(() => toasts.openDialog());
		toastId = id;
		return () => {
			untrack(() => toasts.closeDialog(id));
			// Closing with Escape gives the focus back by itself. A dialog the
			// page removes (after Save, say) would leave it nowhere, so keyboard
			// and screen reader users would start again at the top.
			const focus = document.activeElement;
			const lost = !focus || focus === document.body || box.contains(focus);
			if (lost && opener instanceof HTMLElement && opener.isConnected) {
				opener.focus({ preventScroll: true });
			}
		};
	});

	// A backdrop click targets the <dialog> itself, but so does a click on its
	// padding; only a point outside the box closes it.
	function closeOnBackdrop(event: MouseEvent) {
		if (!dialog || event.target !== dialog) return;
		const box = dialog.getBoundingClientRect();
		const inside =
			event.clientX >= box.left &&
			event.clientX <= box.right &&
			event.clientY >= box.top &&
			event.clientY <= box.bottom;
		if (!inside) dialog.close();
	}
</script>

<!-- The keyboard way to close is Escape, which the browser handles. -->
<dialog
	bind:this={dialog}
	aria-labelledby={titleId}
	tabindex={focusBox ? -1 : undefined}
	onclose={onClose}
	onclick={closeOnBackdrop}
>
	<h2 id={titleId}>{title}</h2>
	<!-- The dialog's content, passed in by the parent between the tags. -->
	{@render children()}
	{#if toastId !== undefined}
		<Toast dialogId={toastId} />
	{/if}
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

	dialog:focus {
		outline: none;
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
