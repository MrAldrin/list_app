<!--
	A ⋮ button that opens a small menu, such as the room menu or the list menu.

	The menu is a `popover`: the browser shows it above the page, and closes
	it on Escape or a click outside. The parent passes the entries as a
	snippet; it gets a `close` function to call before an entry opens a dialog.
-->
<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	let {
		label,
		onOpen,
		children
	}: {
		/** The button's name for screen readers and tests, such as "Room menu". */
		label: string;
		/** Called each time the menu opens. */
		onOpen?: () => void;
		children: Snippet<[close: () => void]>;
	} = $props();

	const menuId = $props.id();
	let button = $state<HTMLButtonElement>();
	let menu = $state<HTMLDivElement>();
	let open = $state(false);

	// A popover sits in the browser's top layer, outside the page layout, so
	// it is placed by hand: below the button, right edges lined up.
	function placeMenu(event: ToggleEvent) {
		open = event.newState === 'open';
		if (!open || !button || !menu) return;
		const box = button.getBoundingClientRect();
		menu.style.top = `${box.bottom + 4}px`;
		menu.style.right = `${Math.max(8, window.innerWidth - box.right)}px`;
		onOpen?.();
	}

	function close() {
		menu?.hidePopover();
	}
</script>

<button
	bind:this={button}
	class="icon"
	type="button"
	aria-label={label}
	aria-expanded={open}
	popovertarget={menuId}
>
	<Icon name="more_vert" />
</button>

<div bind:this={menu} id={menuId} class="menu" popover="auto" ontoggle={placeMenu}>
	{@render children(close)}
</div>

<style>
	.icon {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--text);
	}

	.menu {
		/* Undo the browser's centered popover; `placeMenu` sets top and right. */
		position: fixed;
		inset: auto;
		margin: 0;
		padding: 0.25rem 0;
		min-width: 12rem;
		border: none;
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow);
	}

	/* The entries come from the parent, so these rules reach into its markup. */
	.menu :global(button) {
		display: block;
		width: 100%;
		text-align: left;
		border: none;
		border-radius: 0;
		background: none;
		padding: 0 1rem;
	}

	.menu :global(.danger-text) {
		color: var(--danger);
	}

	.menu :global(hr) {
		margin: 0.25rem 0;
		border: none;
		border-top: 1px solid var(--border);
	}
</style>
