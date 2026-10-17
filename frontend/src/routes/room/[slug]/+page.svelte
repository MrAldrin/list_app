<!--
	The room page (/room/{slug}). The folder name `[slug]` makes the slug a
	route parameter. The page asks for the password when the browser has no
	access, and shows the room's lists once the data layer has loaded them.
-->
<script lang="ts">
	import { page } from '$app/state';
	import {
		admin,
		closeRoom,
		logout,
		notSentYetText,
		openRoom,
		type RoomHandle
	} from '#lib/data/index.ts';
	import PageShell from '#lib/room/PageShell.svelte';
	import RoomHeader from '#lib/room/RoomHeader.svelte';
	import RoomLists from '#lib/room/RoomLists.svelte';
	import ConfirmDialog from '#lib/ui/ConfirmDialog.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	// `$derived` recomputes when what it reads changes (here: the URL).
	const slug = $derived(page.params.slug ?? '');

	let room = $state.raw<RoomHandle | null>(null);
	/** Bumped after signing out, so the shell opens the room afresh. */
	let generation = $state(0);

	// A browser signed in as admin gets a way back to the admin page in the
	// header, also after opening a list and coming back. It never gives room
	// access. A browser that is not signed in as admin sees the normal header.
	let isAdmin = $state(false);
	$effect(() => {
		void slug; // Ask again when another room opens.
		isAdmin = false;
		let current = true;
		admin
			.signedIn()
			.then((signedIn) => {
				if (current) isAdmin = signedIn;
			})
			.catch(() => undefined); // Without an answer, keep the normal header.
		return () => {
			current = false;
		};
	});

	/** Sign-out with changes waiting asks first: they stay here until the next sign-in. */
	let askingSignOut = $state(false);
	function requestSignOut() {
		if ((room?.waitingCount ?? 0) > 0) askingSignOut = true;
		else void signOut();
	}

	async function signOut() {
		askingSignOut = false;
		const result = await logout(slug);
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			return;
		}
		// The old room data is gone; opening again shows the password prompt.
		generation += 1;
	}
</script>

<svelte:head>
	<title>{room?.store.room?.name ?? 'Room'} – ListR</title>
</svelte:head>

<PageShell
	bind:handle={room}
	open={() => openRoom(slug, { hydrateSavedView: true })}
	close={closeRoom}
	reopenKey={generation}
	canSignIn
	connectTitle="Connect to load this room."
	failedTitle="Could not load this room."
>
	{#snippet content(handle)}
		<RoomHeader room={handle} backToAdmin={isAdmin} onLogout={requestSignOut} />
		{#if handle.store.error && !(handle.store.showsOfflineNotice && handle.store.unreachable)}
			<!-- The lists below may be out of date; they stay usable. -->
			<LoadError
				title="Could not load the latest changes."
				detail={handle.store.error}
				onRetry={() => handle.store.refresh()}
			/>
		{/if}
		<RoomLists room={handle} />
	{/snippet}
</PageShell>

{#if askingSignOut && room}
	<ConfirmDialog
		question={notSentYetText(room.waitingCount)}
		detail="After sign-in, choose Send or Discard. Changes older than 30 days need a separate send choice."
		confirmLabel="Sign out"
		onConfirm={signOut}
		onClose={() => (askingSignOut = false)}
	/>
{/if}
