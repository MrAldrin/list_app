<!--
	"Delete Room": asks for the room password to confirm, as NiceGUI. The
	server deletes the room with all its lists and items; this cannot be undone.
-->
<script lang="ts">
	import type { RoomHandle } from '#lib/data/index.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
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
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy || disabled) return;
		busy = true;
		const result = await room.deleteRoom(password);
		busy = false;
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			return;
		}
		password = '';
		onDeleted();
	}
</script>

<Dialog title="Delete Room" {onClose}>
	<form onsubmit={submit} novalidate>
		<p class="warning">
			Warning: This will delete ALL lists and items inside this room. This cannot be undone.
		</p>
		<label for="{id}-password">Enter Room Password to Confirm</label>
		<input
			id="{id}-password"
			type="password"
			bind:value={password}
			autocomplete="current-password"
		/>
		<div class="actions">
			<button type="button" onclick={onClose}>Cancel</button>
			<button class="danger" type="submit" disabled={busy || disabled}>Delete</button>
		</div>
	</form>
</Dialog>

<style>
	form {
		display: grid;
		gap: var(--gap);
	}

	.warning {
		color: var(--text-muted);
		font-size: 0.9rem;
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
