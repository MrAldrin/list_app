<!--
	The admin sign-in (NiceGUI's /admin/login). The password is the app
	password (APP_PASSWORD). It only lives in this field until it is sent; the
	server remembers the sign-in for this browser, not the password.
-->
<script lang="ts">
	import { admin } from '#lib/data/index.ts';

	let { onSignedIn }: { onSignedIn: () => void } = $props();

	let password = $state('');
	let error = $state('');
	let busy = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		const sent = password;
		password = '';
		busy = true;
		const result = await admin.login(sent);
		busy = false;
		if (!result.ok) {
			error = result.message;
			return;
		}
		error = '';
		onSignedIn();
	}
</script>

<form class="card" onsubmit={submit} novalidate>
	<h1>Enter Admin Password</h1>
	<label for="admin-password">Admin Password</label>
	<input
		id="admin-password"
		type="password"
		bind:value={password}
		autocomplete="current-password"
		aria-invalid={error ? 'true' : undefined}
		aria-describedby={error ? 'admin-password-error' : undefined}
	/>
	{#if error}
		<p id="admin-password-error" class="error" role="alert">{error}</p>
	{/if}
	<div class="actions">
		<button class="primary" type="submit" disabled={busy}>Log in</button>
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
