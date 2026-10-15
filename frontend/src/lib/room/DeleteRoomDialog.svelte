<!--
	"Delete Room": asks for the room password to confirm, as NiceGUI. The
	server deletes the room with all its lists and items; this cannot be undone.
-->
<script lang="ts">
	import type { RoomHandle } from '#lib/data/index.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let {
		room,
		disabled = false,
		onDeleted,
		onClose
	}: {
		room: RoomHandle;
		disabled?: boolean;
		onDeleted: () => void;
		onClose: () => void;
	} = $props();

	const id = $props.id();
	let password = $state('');

	async function submit() {
		const result = await room.deleteRoom(password);
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			return;
		}
		password = '';
		onDeleted();
	}
</script>

<FormDialog
	title="Delete Room"
	submitLabel="Delete"
	danger
	submitDisabled={disabled}
	onSubmit={submit}
	{onClose}
>
	<p class="warning">
		Warning: This will delete ALL lists and items inside this room. This cannot be undone.
	</p>
	<label for="{id}-password">Enter Room Password to Confirm</label>
	<input id="{id}-password" type="password" bind:value={password} autocomplete="current-password" />
</FormDialog>

<style>
	.warning {
		color: var(--text-muted);
		font-size: 0.9rem;
	}
</style>
