<!--
	An invitation link (/app/create-room/{token}; NiceGUI: /create-room/{token}).
	Anyone with it can create a room while it is active (docs/room-invitations.md).
	A link that cannot create a room shows NiceGUI's message and no form.
-->
<script lang="ts">
	import { page } from '$app/state';
	import { invitation } from '#lib/data/index.ts';
	import CreateRoomForm from '#lib/invitation/CreateRoomForm.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';

	const token = $derived(page.params.token ?? '');

	let status = $state<'checking' | 'active' | 'unavailable' | 'error'>('checking');
	let error = $state('');

	async function check(link: string) {
		status = 'checking';
		try {
			status = (await invitation.active(link)) ? 'active' : 'unavailable';
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'Something went wrong.';
			status = 'error';
		}
	}

	$effect(() => {
		void check(token);
	});
</script>

<svelte:head>
	<title>Create your room – ListR</title>
</svelte:head>

<main class="page">
	{#if status === 'checking'}
		<p class="muted">Loading…</p>
	{:else if status === 'error'}
		<LoadError
			title="Could not check this invitation."
			detail={error}
			onRetry={() => check(token)}
		/>
	{:else if status === 'unavailable'}
		<div class="card">
			<h1>Create your room</h1>
			<p>This invitation is invalid or no longer active.</p>
			<p>Ask the app admin for a new invitation.</p>
		</div>
	{:else}
		<CreateRoomForm {token} />
	{/if}
</main>

<style>
	main {
		padding-top: 1rem;
	}

	.card {
		display: grid;
		gap: var(--gap);
	}

	h1 {
		font-size: 1.3rem;
	}
</style>
