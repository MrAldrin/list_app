<!--
	"Create your room" from an invitation link (NiceGUI's `creation_form`).
	The server checks the invitation again when the room is created. The
	creator is not signed in: after creating, the room page asks for the new
	password, as in NiceGUI.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { invitation } from '#lib/data/index.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let { token }: { token: string } = $props();

	let name = $state('');
	let password = $state('');
	let confirmation = $state('');
	let busy = $state(false);
	// Once created, or when the link stopped working, the button stays disabled (NiceGUI).
	let done = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy || done) return;
		if (password !== confirmation) {
			toasts.show('Passwords do not match', 'warning');
			return;
		}
		busy = true;
		const result = await invitation.createRoom(token, name, password);
		busy = false;
		if (!result.ok) {
			if (invitation.isUnavailableResult(result)) {
				done = true;
				toasts.show(result.message, 'danger');
				return;
			}
			toasts.show(result.message, 'warning');
			return;
		}
		done = true;
		password = '';
		confirmation = '';
		await goto(resolve('/room/[slug]', { slug: result.result.slug }));
	}
</script>

<form class="card" onsubmit={submit} novalidate>
	<h1>Create your room</h1>
	<p>Choose a password. Anyone you share it with can manage this room.</p>
	<p class="small">The app admin also needs the room password to enter.</p>
	<label for="new-room-name">Room name</label>
	<input id="new-room-name" bind:value={name} maxlength="100" autocomplete="off" />
	<label for="new-room-password">Room password</label>
	<input id="new-room-password" type="password" bind:value={password} autocomplete="new-password" />
	<label for="new-room-confirmation">Confirm password</label>
	<input
		id="new-room-confirmation"
		type="password"
		bind:value={confirmation}
		autocomplete="new-password"
	/>
	<p class="small">Keep your password and room link. Next, sign in to your room.</p>
	<button class="primary" type="submit" disabled={busy || done}>Create room</button>
</form>

<style>
	form {
		display: grid;
		gap: var(--gap);
	}

	h1 {
		font-size: 1.3rem;
	}

	label {
		font-weight: 600;
	}

	.small {
		font-size: 0.9rem;
	}
</style>
