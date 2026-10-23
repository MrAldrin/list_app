<!--
	The admin page (/admin; NiceGUI also had /admin/login, which the server sends here). Without
	admin sign-in it asks for the app password; then it shows every room and
	the creation invitations.
	Admin sign-in lasts 30 minutes and never opens a room by itself.
-->
<script lang="ts">
	import { admin } from '#lib/data/index.ts';
	import AdminLogin from '#lib/admin/AdminLogin.svelte';
	import AdminInvitations from '#lib/admin/AdminInvitations.svelte';
	import AdminRooms from '#lib/admin/AdminRooms.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import Brand from '#lib/ui/Brand.svelte';
	import ThemeToggle from '#lib/ui/ThemeToggle.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let status = $state<'checking' | 'signed_out' | 'signed_in' | 'error'>('checking');
	let error = $state('');

	async function check() {
		try {
			status = (await admin.signedIn()) ? 'signed_in' : 'signed_out';
		} catch (caught) {
			error = caught instanceof Error ? caught.message : 'Something went wrong.';
			status = 'error';
		}
	}

	$effect(() => {
		void check();
	});

	async function signOut() {
		const result = await admin.logout();
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			return;
		}
		status = 'signed_out';
	}
</script>

<svelte:head>
	<title>Admin – ListR</title>
</svelte:head>

<main class="page">
	{#if status === 'checking'}
		<p class="muted">Loading…</p>
	{:else if status === 'error'}
		<LoadError title="Could not check the admin sign-in." detail={error} onRetry={check} />
	{:else if status === 'signed_out'}
		<AdminLogin onSignedIn={() => (status = 'signed_in')} />
	{:else}
		<header>
			<Brand size="1.8rem" />
			<h1 class="visually-hidden">Admin</h1>
			<div class="end">
				<button class="outline" type="button" onclick={signOut}>Sign out of admin</button>
				<ThemeToggle />
			</div>
		</header>
		<p class="muted">Admin access lasts 30 minutes from sign-in. Room logins are separate.</p>
		<AdminRooms onSignedOut={() => (status = 'signed_out')} />
		<AdminInvitations onSignedOut={() => (status = 'signed_out')} />
	{/if}
</main>

<style>
	main {
		padding-top: 1rem;
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 1rem;
	}

	.end {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
</style>
