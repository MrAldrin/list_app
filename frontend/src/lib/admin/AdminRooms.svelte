<!--
	The admin room overview (NiceGUI's /admin): "Create New Room", "Refresh
	rooms" and every room, by name. A room name opens the room page, which
	still asks for the room password. The "Reset password" button resets the
	room password; "Delete" deletes the room (see AdminDeleteRoomDialog).
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { admin, type Room } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { adminRoomHref } from './admin-links.ts';
	import AdminDeleteRoomDialog from './AdminDeleteRoomDialog.svelte';
	import CreateRoomDialog from './CreateRoomDialog.svelte';
	import { showAdminFailure } from './failure.ts';
	import ResetPasswordDialog from './ResetPasswordDialog.svelte';

	let { onSignedOut }: { onSignedOut: () => void } = $props();

	let rooms = $state.raw<Room[] | null>(null);
	let error = $state('');
	let creating = $state(false);
	let resetting = $state.raw<Room | null>(null);
	let deleting = $state.raw<Room | null>(null);

	async function load() {
		const result = await admin.rooms();
		if (result.ok) {
			rooms = result.result;
			error = '';
			return;
		}
		if (admin.isSignedOut(result)) {
			showAdminFailure(result, onSignedOut);
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
		deleting = null;
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

	function deleteDone() {
		deleting = null;
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
	<ul class="list-rows">
		{#each rooms as room (room.slug)}
			<li class="card list-row">
				<a class="list-row-link" href={adminRoomHref(room.slug)}><span>{room.name}</span></a>
				<button
					class="icon"
					type="button"
					aria-label="Reset password of {room.name}"
					onclick={() => (resetting = room)}
				>
					<Icon name="key" />
					Reset password
				</button>
				<button
					class="icon delete"
					type="button"
					aria-label="Delete room {room.name}"
					onclick={() => (deleting = room)}
				>
					<Icon name="delete" />
					Delete
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

{#if deleting}
	<AdminDeleteRoomDialog
		room={deleting}
		onDone={deleteDone}
		onSignedOut={signedOut}
		onClose={() => (deleting = null)}
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

	/* Icon and text; the text keeps the button easy to understand and to hit. */
	.icon {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0 0.5rem;
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	/* Beats .icon, which sets the muted colour. */
	.icon.delete {
		color: var(--danger);
	}
</style>
