<!--
	The start page (/). Like NiceGUI's `/`, it is a router: if this browser
	signed in to a room before, it goes straight to that room. Otherwise it
	asks for the room link or code, and offers the admin page.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { lastRoom } from '#lib/data/index.ts';
	import { roomSlugFromInput } from '#lib/room-link.ts';

	// `$state` makes a variable reactive: the page updates when it changes.
	let checking = $state(true);
	let warning = $state('');
	let roomInput = $state('');
	let error = $state('');

	function openRoomPage(slug: string, replace = false) {
		// `resolve` adds the app's base path (none: the app is at /) to the route.
		// `replaceState` keeps the start page out of the back-button history.
		return goto(resolve('/room/[slug]', { slug }), { replaceState: replace });
	}

	let retrying = $state(false);

	/** Goes to the last room of this browser, if any. */
	async function checkLastRoom() {
		try {
			const slug = await lastRoom();
			// Remembering a room is routing only: the room page asks for the
			// password if this browser has no access any more.
			if (slug) return openRoomPage(slug, true);
			warning = '';
		} catch {
			// Server down or busy: the form still works, and Retry asks again.
			warning = 'Could not check your last room. Open your room link to continue.';
		}
		checking = false;
	}

	async function retry() {
		retrying = true;
		await checkLastRoom();
		retrying = false;
	}

	// `$effect` runs after the page is shown in the browser; here once.
	$effect(() => {
		void checkLastRoom();
	});

	function submit(event: SubmitEvent) {
		// Stop the browser from sending the form and reloading the page;
		// we handle it here instead.
		event.preventDefault();
		if (!roomInput.trim()) {
			error = 'Enter a room link or code';
			return;
		}
		const slug = roomSlugFromInput(roomInput);
		if (!slug) {
			error = 'Invalid room link. Check the link/code.';
			return;
		}
		error = '';
		void openRoomPage(slug);
	}
</script>

<svelte:head>
	<title>ListR</title>
</svelte:head>

<main class="page">
	{#if checking}
		<p class="muted">Loading…</p>
	{:else}
		<!-- A <form> makes Enter in the field submit, with no extra code. -->
		<form class="card" onsubmit={submit} novalidate>
			<h1>Open your room link to continue</h1>
			<p class="muted">Connect to load a saved room, or paste your room link or code.</p>
			{#if warning}
				<div class="warning-row">
					<p class="warning" role="status">{warning}</p>
					<button class="outline" type="button" disabled={retrying} onclick={retry}>
						{retrying ? 'Retrying…' : 'Retry'}
					</button>
				</div>
			{/if}
			<label for="room-input">Room link or code</label>
			<input
				id="room-input"
				bind:value={roomInput}
				autocomplete="off"
				autocapitalize="none"
				spellcheck="false"
				aria-invalid={error ? 'true' : undefined}
				aria-describedby={error ? 'room-error' : undefined}
			/>
			{#if error}
				<p id="room-error" class="error" role="alert">{error}</p>
			{/if}
			<div class="actions">
				<button class="primary" type="submit">Open Room</button>
				<button class="outline" type="button" onclick={() => goto(resolve('/admin'))}>
					Admin
				</button>
			</div>
		</form>
	{/if}
</main>

<style>
	/* These styles only apply to this page (Svelte adds a unique class). */
	main {
		padding-top: 15vh;
	}

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

	.warning {
		color: var(--warning);
	}

	.warning-row {
		display: flex;
		align-items: center;
		gap: var(--gap);
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
