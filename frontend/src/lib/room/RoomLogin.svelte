<!--
	The room password prompt. The password only lives in this field until it is
	sent; the server answers with an HTTP-only cookie that JavaScript never sees.
-->
<script lang="ts">
	import type { ActionResult } from '#lib/data/index.ts';

	// `$props()` lists what the parent passes in: <RoomLogin onLogin={…} />.
	let { onLogin }: { onLogin: (password: string) => Promise<ActionResult<unknown>> } = $props();

	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		const sent = password;
		// Clear the field at once, so the password is not kept on the page.
		password = '';
		busy = true;
		const result = await onLogin(sent);
		busy = false;
		error = result.ok ? '' : result.message;
	}
</script>

<form class="card" onsubmit={submit} novalidate>
	<h1>Enter Room Password</h1>
	<label for="room-password">Room Password</label>
	<input
		id="room-password"
		type="password"
		bind:value={password}
		autocomplete="current-password"
		aria-invalid={error ? 'true' : undefined}
		aria-describedby={error ? 'password-error' : undefined}
	/>
	{#if error}
		<p id="password-error" class="error" role="alert">{error}</p>
	{/if}
	<div class="actions">
		<button class="primary" type="submit" disabled={busy}>Enter</button>
	</div>
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

	.error {
		color: var(--danger);
	}

	.actions {
		display: flex;
		justify-content: flex-end;
	}
</style>
