<!--
	A card with one password field and a submit button, for example "Enter Room
	Password". The password only lives in this field until it is sent. A failed
	answer shows its message under the field. The button is disabled while the
	answer is on its way.
-->
<script lang="ts">
	import type { ActionResult } from '#lib/data/index.ts';

	let {
		title,
		label,
		inputId,
		errorId,
		buttonText,
		onSubmit
	}: {
		title: string;
		label: string;
		inputId: string;
		errorId: string;
		buttonText: string;
		onSubmit: (password: string) => Promise<ActionResult<unknown>>;
	} = $props();

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
		const result = await onSubmit(sent);
		busy = false;
		error = result.ok ? '' : result.message;
	}
</script>

<form class="card" onsubmit={submit} novalidate>
	<h1>{title}</h1>
	<label for={inputId}>{label}</label>
	<input
		id={inputId}
		type="password"
		bind:value={password}
		autocomplete="current-password"
		aria-invalid={error ? 'true' : undefined}
		aria-describedby={error ? errorId : undefined}
	/>
	{#if error}
		<p id={errorId} class="error" role="alert">{error}</p>
	{/if}
	<div class="actions">
		<button class="primary" type="submit" disabled={busy}>{buttonText}</button>
	</div>
</form>
