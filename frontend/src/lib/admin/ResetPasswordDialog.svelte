<!--
	"Admin reset of room password: {room}": a new room password, without the
	current one. Every device signed in to the room is logged out and must use
	the new password (the server revokes all room access tokens). Share links
	and the room link keep working. Admin sign-in is not room access. A room that is gone closes the dialog and reloads the rooms.
-->
<script lang="ts">
	import { admin, type Room } from '#lib/data/index.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

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
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		const result = await admin.resetPassword(room.slug, password);
		busy = false;
		if (result.ok) {
			password = '';
			toasts.show('Password reset successfully', 'success');
			onDone();
		} else if (result.code === 'room_unavailable') {
			toasts.show(result.message, 'danger');
			onDone();
		} else {
			// A blank password or a lost connection: keep the dialog to fix it.
			toasts.show(result.message, 'warning');
			if (admin.isSignedOut(result)) onSignedOut();
		}
	}
</script>

<Dialog title="Admin reset of room password: {room.name}" {onClose}>
	<form onsubmit={submit} novalidate>
		<p class="explain">
			Sets a new password for this room without asking for the old one. Everyone who is signed in to
			the room is logged out on every device and must sign in with the new password. Share links to
			its lists keep working.
		</p>
		<label for="{id}-password">New Room Password</label>
		<input id="{id}-password" type="password" bind:value={password} autocomplete="new-password" />
		<div class="actions">
			<button type="button" onclick={onClose}>Cancel</button>
			<button class="danger" type="submit" disabled={busy}>Reset</button>
		</div>
	</form>
</Dialog>

<style>
	form {
		display: grid;
		gap: var(--gap);
	}

	.explain {
		margin: 0;
		color: var(--text-muted);
	}

	label {
		font-weight: 600;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
