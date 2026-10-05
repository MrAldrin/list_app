<!--
	The admin room overview (NiceGUI's /admin): "Create New Room", "Refresh
	rooms" and every room, by name. A room name opens the room page, which
	still asks for the room password. The key button resets the password.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { admin, type Room } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import { adminRoomHref } from './admin-links.ts';
	import CreateRoomDialog from './CreateRoomDialog.svelte';
	import ResetPasswordDialog from './ResetPasswordDialog.svelte';

	let { onSignedOut }: { onSignedOut: () => void } = $props();

	let rooms = $state.raw<Room[] | null>(null);
	let error = $state('');
	let creating = $state(false);
	let resetting = $state.raw<Room | null>(null);

	async function load() {
		const result = await admin.rooms();
		if (result.ok) {
			rooms = result.result;
			error = '';
			return;
		}
		if (admin.isSignedOut(result)) {
			toasts.show(result.message, 'warning');
			onSignedOut();
			return;
		}
		error = result.message;
	}

	$effect(() => {
		void load();
	});

	function signedOut() {
		creating = false;
		resetting = null;
		onSignedOut();
	}

	async function created(room: Room) {
		creating = false;
		await goto(adminRoomHref(room.slug));
	}

	function resetDone() {
		resetting = null;
		void load();
	}
</script>

<button class="outline add" type="button" onclick={() => (creating = true)}>
	<Icon name="add" />
	Create New Room
</button>

<button class="refresh" type="button" onclick={load}>
	<Icon name="refresh" />
	Refresh rooms
</button>

{#if error}
	<LoadError title="Could not load the rooms." detail={error} onRetry={load} />
{/if}

{#if rooms === null}
	{#if !error}<p class="muted">Loading…</p>{/if}
{:else if rooms.length === 0}
	<p class="muted empty">No rooms yet. Create your first one!</p>
{:else}
	<ul>
		{#each rooms as room (room.slug)}
			<li class="card">
				<a href={adminRoomHref(room.slug)}><span>{room.name}</span></a>
				<button
					class="icon"
					type="button"
					aria-label="Reset password of {room.name}"
					onclick={() => (resetting = room)}
				>
					<Icon name="key" />
				</button>
			</li>
		{/each}
	</ul>
{/if}

{#if creating}
	<CreateRoomDialog
		onCreated={created}
		onSignedOut={signedOut}
		onClose={() => (creating = false)}
	/>
{/if}

{#if resetting}
	<ResetPasswordDialog
		room={resetting}
		onDone={resetDone}
		onSignedOut={signedOut}
		onClose={() => (resetting = null)}
	/>
{/if}

<style>
	.add {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		width: 100%;
		margin-bottom: 1rem;
		color: var(--primary);
		font-weight: 600;
	}

	.refresh {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0 0.5rem;
		margin-bottom: 0.5rem;
		color: var(--primary);
		font-size: 0.9rem;
	}

	.empty {
		font-style: italic;
		text-align: center;
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}

	li {
		display: flex;
		align-items: center;
		padding: 0.25rem;
	}

	/* The name is a link that fills the row, so the whole row is easy to tap. */
	a {
		flex: 1;
		min-width: 0;
		min-height: var(--touch);
		display: flex;
		align-items: center;
		padding: 0 0.75rem;
		color: var(--text);
		font-size: 1.1rem;
		text-decoration: none;
	}

	a span {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.icon {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--text-muted);
	}
</style>
