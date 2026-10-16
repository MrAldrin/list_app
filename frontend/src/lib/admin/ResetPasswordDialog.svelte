<!--
	"Admin reset of room password: {room}": a new room password, without the
	current one. Every device signed in to the room is logged out and must use
	the new password (the server revokes all room access tokens). Share links
	and the room link keep working. Admin sign-in is not room access. A room that is gone closes the dialog and reloads the rooms.
-->
<script lang="ts">
	import { admin, type Room } from '#lib/data/index.ts';
	import { shortPasswordMessage } from '#lib/ui/field-limits.ts';
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
		/** After a reset, or when the room is gone: close and reload the rooms. */
		onDone: () => void;
		onSignedOut: () => void;
		onClose: () => void;
	} = $props();

	const id = $props.id();
	let password = $state('');

	async function submit() {
		const tooShort = shortPasswordMessage(password);
		if (tooShort) {
			toasts.show(tooShort, 'warning');
			return;
		}
		const result = await admin.resetPassword(room.slug, password);
		if (result.ok) {
			password = '';
			toasts.show('Password reset successfully', 'success');
			onDone();
		} else if (result.code === 'room_unavailable') {
			toasts.show(result.message, 'danger');
			onDone();
		} else {
			// A blank password or a lost connection: keep the dialog to fix it.
			showAdminFailure(result, onSignedOut);
		}
	}
</script>

<FormDialog
	title="Admin reset of room password: {room.name}"
	submitLabel="Reset"
	danger
	onSubmit={submit}
	{onClose}
>
	<p class="explain">
		Sets a new password for this room without asking for the old one. Everyone who is signed in to
		the room is logged out on every device and must sign in with the new password. Share links to
		its lists keep working.
	</p>
	<label for="{id}-password">New Room Password</label>
	<input id="{id}-password" type="password" bind:value={password} autocomplete="new-password" />
</FormDialog>

<style>
	.explain {
		margin: 0;
		color: var(--text-muted);
	}
</style>
