<!--
	"New Room" on the admin page: a name and the room password. The server
	checks both (docs/api.md, "Admin"); its message shows as a toast and the
	dialog stays open. Enter in the password field creates the room.
-->
<script lang="ts">
	import { admin, type ActionResult, type Room } from '#lib/data/index.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let {
		onCreated,
		onSignedOut,
		onClose
	}: {
		onCreated: (room: Room) => void;
		onSignedOut: () => void;
		onClose: () => void;
	} = $props();

	const id = $props.id();
	let name = $state('');
	let password = $state('');
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		const result: ActionResult<Room> = await admin.createRoom(name, password);
		busy = false;
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			if (admin.isSignedOut(result)) onSignedOut();
			return;
		}
		password = '';
		toasts.show('Room created', 'success');
		onCreated(result.result);
	}
</script>

<Dialog title="New Room" {onClose}>
	<form onsubmit={submit} novalidate>
		<label for="{id}-name">Room name</label>
		<input id="{id}-name" bind:value={name} autocomplete="off" />
		<label for="{id}-password">Password</label>
		<input id="{id}-password" type="password" bind:value={password} autocomplete="new-password" />
		<div class="actions">
			<button type="button" onclick={onClose}>Cancel</button>
			<button class="primary" type="submit" disabled={busy}>Create</button>
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
