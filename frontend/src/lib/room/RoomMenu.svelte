<!--
	The room menu (the ⋮ button in the room header): share the room link,
	home-screen install help, the Rooms section (switch with one tap, or add a
	room), rename the room, change its password, delete it, log out. Texts and
	order match NiceGUI's room menu, except the Rooms section. Each entry closes
	the menu and opens a dialog.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { RoomHandle } from '#lib/data/index.ts';
	import InstallHelpDialog from '#lib/install/InstallHelpDialog.svelte';
	import MenuButton from '#lib/ui/MenuButton.svelte';
	import NeedsConnection from '#lib/ui/NeedsConnection.svelte';
	import ThemeMenuItem from '#lib/ui/ThemeMenuItem.svelte';
	import NameDialog from '#lib/ui/NameDialog.svelte';
	import ShareDialog from '#lib/ui/ShareDialog.svelte';
	import { absoluteUrl, shareLinkWithToast } from '#lib/ui/share.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import ChangePasswordDialog from './ChangePasswordDialog.svelte';
	import DeleteRoomDialog from './DeleteRoomDialog.svelte';
	import { forgetRoom, readRememberedRooms, type RememberedRoom } from './remembered-rooms.ts';

	let {
		room,
		backToAdmin = false,
		onLogout
	}: { room: RoomHandle; backToAdmin?: boolean; onLogout: () => void } = $props();

	/** Password and delete are checked by the server: they need a connection. */
	const online = $derived(room.store.canWrite);
	const hintId = $props.id();
	let dialog = $state<'share' | 'install' | 'rename' | 'password' | 'delete' | null>(null);
	let shareUrl = $state('');
	/** Read as the menu opens: other rooms may have changed. */
	let remembered = $state<RememberedRoom[]>([]);

	function menuOpened() {
		remembered = readRememberedRooms().filter((item) => item.slug !== room.slug);
	}

	function choose(close: () => void, next: 'install' | 'rename' | 'password' | 'delete') {
		close();
		dialog = next;
	}

	/** The room link needs the password too; it is not a share link. */
	async function share(close: () => void) {
		close();
		const url = absoluteUrl(resolve('/room/[slug]', { slug: room.slug }));
		if (!(await shareLinkWithToast(url, 'room'))) return;
		shareUrl = url;
		dialog = 'share';
	}

	async function rename(name: string) {
		const result = await room.renameRoom(name);
		// A rejection (such as an empty name) shows as a toast from the store.
		if (result.ok) dialog = null;
	}

	/** Opens another remembered room. It asks for its password if access is gone. */
	function switchRoom(close: () => void, slug: string) {
		close();
		void goto(resolve('/room/[slug]', { slug }));
	}

	/** Opens the start page to enter another room. `?add` skips the jump to the last room. */
	function addRoom(close: () => void) {
		close();
		void goto(`${resolve('/')}?add`);
	}

	async function deleted() {
		dialog = null;
		forgetRoom(room.slug);
		toasts.show('Room deleted', 'danger');
		// As NiceGUI: back to the admin page when the room was opened from there.
		await goto(backToAdmin ? resolve('/admin') : resolve('/'));
	}
</script>

<MenuButton label="Room menu" onOpen={menuOpened}>
	{#snippet children(close)}
		<button type="button" onclick={() => share(close)}>Share Room</button>
		<button type="button" onclick={() => choose(close, 'install')}>Add to Home Screen</button>
		<ThemeMenuItem {close} />
		<hr />
		<div class="rooms" role="group" aria-label="Rooms">
			<p class="heading">Rooms</p>
			{#each remembered as other (other.slug)}
				<button type="button" onclick={() => switchRoom(close, other.slug)}>
					{other.name}
				</button>
			{/each}
			<button type="button" onclick={() => addRoom(close)}>+ Add room</button>
		</div>
		<hr />
		<button type="button" disabled={!room.store.canEdit} onclick={() => choose(close, 'rename')}>
			Rename Room
		</button>
		<!-- These need a connection: the server checks the password. -->
		<button
			type="button"
			disabled={!online}
			title={online ? undefined : 'Needs a connection'}
			aria-describedby={online ? undefined : hintId}
			onclick={() => choose(close, 'password')}
		>
			Change Password
		</button>
		<button
			type="button"
			class="danger-text"
			disabled={!online}
			title={online ? undefined : 'Needs a connection'}
			aria-describedby={online ? undefined : hintId}
			onclick={() => choose(close, 'delete')}
		>
			Delete Room
		</button>
		<NeedsConnection id={hintId} show={!online} />
		<hr />
		<button
			type="button"
			onclick={() => {
				close();
				onLogout();
			}}>Log out</button
		>
	{/snippet}
</MenuButton>

{#if dialog === 'share'}
	<ShareDialog kind="room" url={shareUrl} onClose={() => (dialog = null)} />
{:else if dialog === 'install'}
	<InstallHelpDialog onClose={() => (dialog = null)} />
{:else if dialog === 'rename'}
	<NameDialog
		title="Rename Room"
		label="New name"
		initial={room.store.room?.name ?? ''}
		saveDisabled={!room.store.canEdit}
		onSave={rename}
		onClose={() => (dialog = null)}
	/>
{:else if dialog === 'password'}
	<ChangePasswordDialog {room} disabled={!online} onClose={() => (dialog = null)} />
{:else if dialog === 'delete'}
	<DeleteRoomDialog {room} disabled={!online} onDeleted={deleted} onClose={() => (dialog = null)} />
{/if}

<style>
	.heading {
		margin: 0;
		padding: 0.25rem 1rem 0;
		color: var(--text-muted);
		font-size: 0.85em;
	}
</style>
