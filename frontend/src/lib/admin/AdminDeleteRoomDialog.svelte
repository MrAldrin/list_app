<!--
	"Admin delete of room: {room}": deletes the room with all its lists and
	items, without its password. The admin must type the room name exactly to
	enable Delete. The room's open pages then need the room password, as after
	a normal delete. A room that is gone closes the dialog and reloads the rooms.
-->
<script lang="ts">
	import { admin, type Room } from '#lib/data/index.ts';
	import { forgetRoom } from '#lib/room/remembered-rooms.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import { showAdminFailure } from './failure.ts';

	let {
		room,
		onDone,
		onSignedOut,
		onClose
	}: {
		room: Room;
		/** After a delete, or when the room is gone: close and reload the rooms. */
		onDone: () => void;
		onSignedOut: () => void;
		onClose: () => void;
	} = $props();

	const id = $props.id();
	let typed = $state('');

	async function submit() {
		const result = await admin.deleteRoom(room.slug);
		if (result.ok) {
			forgetRoom(room.slug);
			toasts.show('Room deleted', 'success');
			onDone();
		} else if (result.code === 'room_unavailable') {
			forgetRoom(room.slug);
			toasts.show(result.message, 'danger');
			onDone();
		} else {
			// A lost connection: keep the dialog so the admin can try again.
			showAdminFailure(result, onSignedOut);
		}
	}
</script>

<FormDialog
	title="Admin delete of room: {room.name}"
	submitLabel="Delete"
	danger
	submitDisabled={typed !== room.name}
	onSubmit={submit}
	{onClose}
>
	<p class="warning">
		This deletes the room <strong>{room.name}</strong> with ALL its lists and items. Everyone who is signed
		in to it is logged out, and its share links stop working. This cannot be undone.
	</p>
	<label for="{id}-name">Type the room name to confirm: {room.name}</label>
	<input id="{id}-name" bind:value={typed} autocomplete="off" />
</FormDialog>

<style>
	.warning {
		margin: 0;
		color: var(--text-muted);
	}
</style>
