<!--
	"Admin Reset: {room}": a new room password, without the current one.
	Every device of the room must then sign in again. Texts match NiceGUI's
	admin page. A room that is gone closes the dialog and reloads the rooms.
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

<Dialog title="Admin Reset: {room.name}" {onClose}>
	<form onsubmit={submit} novalidate>
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

	label {
		font-weight: 600;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
