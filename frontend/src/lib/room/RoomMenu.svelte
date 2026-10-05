<!--
	The room menu (the ⋮ button in the room header): rename the room, change
	its password, delete it. Texts match NiceGUI's room menu.

	The menu is a `popover`: the browser shows it above the page, and closes
	it on Escape or a click outside. Each entry closes the menu and opens a
	dialog.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { RoomHandle } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import NameDialog from '#lib/ui/NameDialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import ChangePasswordDialog from './ChangePasswordDialog.svelte';
	import DeleteRoomDialog from './DeleteRoomDialog.svelte';

	let { room }: { room: RoomHandle } = $props();

	const menuId = $props.id();
	let button = $state<HTMLButtonElement>();
	let menu = $state<HTMLDivElement>();
	let open = $state(false);
	let dialog = $state<'rename' | 'password' | 'delete' | null>(null);

	// A popover sits in the browser's top layer, outside the page layout, so
	// it is placed by hand: below the button, right edges lined up.
	function placeMenu(event: ToggleEvent) {
		open = event.newState === 'open';
		if (!open || !button || !menu) return;
		const box = button.getBoundingClientRect();
		menu.style.top = `${box.bottom + 4}px`;
		menu.style.right = `${Math.max(8, window.innerWidth - box.right)}px`;
	}

	function choose(next: 'rename' | 'password' | 'delete') {
		menu?.hidePopover();
		dialog = next;
	}

	async function rename(name: string) {
		const result = await room.renameRoom(name);
		// A rejection (such as an empty name) shows as a toast from the store.
		if (result.ok) dialog = null;
	}

	async function deleted() {
		dialog = null;
		toasts.show('Room deleted', 'danger');
		await goto(resolve('/'));
	}
</script>

<button
	bind:this={button}
	class="icon"
	type="button"
	aria-label="Room menu"
	aria-expanded={open}
	popovertarget={menuId}
>
	<Icon name="more_vert" />
</button>

<div bind:this={menu} id={menuId} class="menu" popover="auto" ontoggle={placeMenu}>
	<button type="button" onclick={() => choose('rename')}>Rename Room</button>
	<button type="button" onclick={() => choose('password')}>Change Password</button>
	<button type="button" class="delete" onclick={() => choose('delete')}>Delete Room</button>
</div>

{#if dialog === 'rename'}
	<NameDialog
		title="Rename Room"
		label="New name"
		initial={room.store.room?.name ?? ''}
		onSave={rename}
		onClose={() => (dialog = null)}
	/>
{:else if dialog === 'password'}
	<ChangePasswordDialog {room} onClose={() => (dialog = null)} />
{:else if dialog === 'delete'}
	<DeleteRoomDialog {room} onDeleted={deleted} onClose={() => (dialog = null)} />
{/if}

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

	.menu button {
		display: block;
		width: 100%;
		text-align: left;
		border: none;
		border-radius: 0;
		background: none;
		padding: 0 1rem;
	}

	.menu .delete {
		color: var(--danger);
	}
</style>
