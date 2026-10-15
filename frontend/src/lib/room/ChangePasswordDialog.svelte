<!--
	"Change Room Password": the current and the new password. The server
	checks both (docs/api.md, "Room management"). Afterwards this browser
	stays signed in; every other device must sign in with the new password.
	The passwords live only in these fields until they are sent.
-->
<script lang="ts">
	import type { RoomHandle } from '#lib/data/index.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let {
		room,
		disabled = false,
		onClose
	}: { room: RoomHandle; disabled?: boolean; onClose: () => void } = $props();

	const id = $props.id();
	let current = $state('');
	let next = $state('');

	async function submit() {
		const result = await room.changePassword(current, next);
		if (!result.ok) {
			// Keep the dialog open, so a typo can be fixed.
			toasts.show(result.message, 'warning');
			return;
		}
		current = '';
		next = '';
		toasts.show('Password changed successfully', 'success');
		onClose();
	}
</script>

<FormDialog
	title="Change Room Password"
	submitLabel="Change"
	submitDisabled={disabled}
	onSubmit={submit}
	{onClose}
>
	<label for="{id}-current">Current Password</label>
	<input id="{id}-current" type="password" bind:value={current} autocomplete="current-password" />
	<label for="{id}-new">New Password</label>
	<input id="{id}-new" type="password" bind:value={next} autocomplete="new-password" />
</FormDialog>
