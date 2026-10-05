<!--
	The room menu (the ⋮ button in the room header): share the room link,
	rename the room, change its password, delete it. Texts and order match
	NiceGUI's room menu. Each entry closes the menu and opens a dialog.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { RoomHandle } from '#lib/data/index.ts';
	import MenuButton from '#lib/ui/MenuButton.svelte';
	import NameDialog from '#lib/ui/NameDialog.svelte';
	import ShareDialog from '#lib/ui/ShareDialog.svelte';
	import { absoluteUrl, shareNatively } from '#lib/ui/share.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import ChangePasswordDialog from './ChangePasswordDialog.svelte';
	import DeleteRoomDialog from './DeleteRoomDialog.svelte';

	let { room }: { room: RoomHandle } = $props();

	let dialog = $state<'share' | 'rename' | 'password' | 'delete' | null>(null);
	let shareUrl = $state('');

	function choose(close: () => void, next: 'rename' | 'password' | 'delete') {
		close();
		dialog = next;
	}

	/** The room link needs the password too; it is not a share link. */
	async function share(close: () => void) {
		close();
		const url = absoluteUrl(resolve('/room/[slug]', { slug: room.slug }));
		if ((await shareNatively('room', url)) !== 'fallback') return;
		shareUrl = url;
		dialog = 'share';
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

<MenuButton label="Room menu">
	{#snippet children(close)}
		<button type="button" onclick={() => share(close)}>Share Room</button>
		<hr />
		<button type="button" onclick={() => choose(close, 'rename')}>Rename Room</button>
		<button type="button" onclick={() => choose(close, 'password')}>Change Password</button>
		<button type="button" class="danger-text" onclick={() => choose(close, 'delete')}>
			Delete Room
		</button>
	{/snippet}
</MenuButton>

{#if dialog === 'share'}
	<ShareDialog kind="room" url={shareUrl} onClose={() => (dialog = null)} />
{:else if dialog === 'rename'}
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
