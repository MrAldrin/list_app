<!--
	"New Room" on the admin page: a name and the room password. The server
	checks both (docs/api.md, "Admin"); its message shows as a toast and the
	dialog stays open. Enter in the password field creates the room.
-->
<script lang="ts">
	import { MAX_NAME_LENGTH } from '#lib/ui/field-limits.ts';
	import { admin, type ActionResult, type Room } from '#lib/data/index.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
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

	async function submit() {
		const result: ActionResult<Room> = await admin.createRoom(name, password);
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

<FormDialog title="New Room" submitLabel="Create" onSubmit={submit} {onClose}>
	<label for="{id}-name">Room name</label>
	<input id="{id}-name" bind:value={name} maxlength={MAX_NAME_LENGTH} autocomplete="off" />
	<label for="{id}-password">Password</label>
	<input id="{id}-password" type="password" bind:value={password} autocomplete="new-password" />
</FormDialog>
