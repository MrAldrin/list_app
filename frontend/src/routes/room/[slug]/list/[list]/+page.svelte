<!--
	The list page (/app/room/{room}/list/{list}). The room is in the URL because
	the data layer loads a whole room at once (the changes feed is per room).
	The page asks for the room password when needed, like the room page, and
	shows a clear message when the list is gone or not in this room.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { closeRoom, openRoom, type Item, type List, type RoomHandle } from '#lib/data/index.ts';
	import AddItem from '#lib/list/AddItem.svelte';
	import ItemDialog from '#lib/list/ItemDialog.svelte';
	import ItemRow from '#lib/list/ItemRow.svelte';
	import ListHeader from '#lib/list/ListHeader.svelte';
	import ListOptions from '#lib/list/ListOptions.svelte';
	import {
		addFeedback,
		showsQuantity,
		UNAVAILABLE_LIST_MESSAGE,
		UNDO_DURATION,
		type QuantityView
	} from '#lib/list/items.ts';
	import RoomLogin from '#lib/room/RoomLogin.svelte';
	import { showNoticesAsToasts } from '#lib/ui/notice-toasts.svelte.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	const roomSlug = $derived(page.params.slug ?? '');
	const listSlug = $derived(page.params.list ?? '');
	const roomHref = $derived(resolve('/room/[slug]', { slug: roomSlug }));

	let room = $state.raw<RoomHandle | null>(null);

	// Open the room while this page is shown (see the room page).
	$effect(() => {
		const handle = openRoom(roomSlug);
		room = handle;
		return () => closeRoom(handle);
	});

	showNoticesAsToasts(() => room?.store);

	const list = $derived(room?.store.listBySlug(listSlug));

	// What this page shows; not saved, as in NiceGUI.
	let optionsOpen = $state(false);
	let view = $state<QuantityView>({ showQuantities: false, onlyAboveOne: false });
	/** The item in the edit dialog, as it was when the dialog opened. */
	let editing = $state.raw<Item | null>(null);

	// "Hide after N days" depends on the clock, so the visible items are
	// worked out again every minute (NiceGUI does the same).
	let now = $state(new Date());
	$effect(() => {
		const timer = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(timer);
	});

	async function addItem(target: List, name: string): Promise<boolean> {
		const result = await room!.addItem(target, name);
		if (result.ok) {
			const feedback = addFeedback(result.result.outcome, name);
			toasts.show(feedback.message, feedback.kind);
			return true;
		}
		// A rejection is shown by the store as a toast. NiceGUI clears the
		// field also when the item is already on the list.
		return result.code === 'duplicate_active';
	}

	function toggle(item: Item, done: boolean) {
		void room!.setDone(item, done);
	}

	function changeQuantity(item: Item, delta: number) {
		void room!.changeQuantity(item, delta);
	}

	async function saveItem(
		item: Item,
		changes: { name: string; description: string; quantity: number }
	) {
		const result = await room!.editItem(item, changes);
		// A blank or duplicate name keeps the dialog open to fix it (the store
		// shows why). It closes when the item or the list is gone.
		if (result.ok || result.code === 'item_not_found' || result.code === 'list_unavailable') {
			editing = null;
		}
	}

	/** Deletes at once and offers "Undo" for a few seconds. */
	function deleteItem(item: Item) {
		editing = null;
		const handle = room!;
		const deleted = handle.deleteItem(item);
		const toastId = toasts.show(`Deleted ${item.name}`, 'danger', {
			duration: UNDO_DURATION,
			action: { label: 'Undo', run: () => void undoDelete(handle, item) }
		});
		void deleted.then((result) => {
			if (!result.ok) toasts.dismiss(toastId);
		});
	}

	async function undoDelete(handle: RoomHandle, item: Item) {
		const result = await handle.restoreItem(item.uid);
		if (result.ok) toasts.show(`Restored ${item.name}`, 'success');
		// "Cannot undo: item name already exists" comes from the store.
		else if (result.code === 'undo_unavailable') toasts.show(result.message, 'warning');
	}
</script>

<svelte:head>
	<title>{list?.name ?? 'List'} – ListR</title>
</svelte:head>

<main class="page">
	{#if !room || room.store.status === 'loading'}
		<p class="muted">Loading…</p>
	{:else if room.store.status === 'auth_required'}
		<RoomLogin onLogin={(password) => room!.login(password)} />
	{:else if room.store.status === 'error'}
		<div class="card problem">
			<p>Could not verify room access. Please retry.</p>
			<button class="outline" type="button" onclick={() => room?.store.refresh()}>Retry</button>
		</div>
	{:else if !list}
		<div class="card problem" role="status">
			<p>{UNAVAILABLE_LIST_MESSAGE}</p>
			<a href={roomHref}>Back to room</a>
		</div>
	{:else}
		{@const current = list}
		<ListHeader
			name={current.name}
			{roomHref}
			{optionsOpen}
			onToggleOptions={() => (optionsOpen = !optionsOpen)}
		/>
		{#if room.store.error}
			<!-- The items below may be out of date; they stay usable. -->
			<div class="card problem" role="status">
				<p>Could not load the latest changes.</p>
				<button class="outline" type="button" onclick={() => room?.store.refresh()}>Retry</button>
			</div>
		{/if}
		{#if optionsOpen}
			<ListOptions bind:view />
		{/if}
		<AddItem items={room.store.itemsOf(current.uid)} onAdd={(name) => addItem(current, name)} />
		<ul class="items">
			{#each room.store.visibleItemsOf(current.uid, now) as item (item.uid)}
				<ItemRow
					{item}
					showQuantity={showsQuantity(item.quantity, view)}
					showDelete={optionsOpen}
					onToggle={(done) => toggle(item, done)}
					onQuantity={(delta) => changeQuantity(item, delta)}
					onOpen={() => (editing = item)}
					onDelete={() => deleteItem(item)}
				/>
			{/each}
		</ul>
		{#if editing}
			{@const item = editing}
			<ItemDialog
				{item}
				onSave={(changes) => saveItem(item, changes)}
				onDelete={() => deleteItem(item)}
				onClose={() => (editing = null)}
			/>
		{/if}
	{/if}
</main>

<style>
	.problem {
		display: grid;
		gap: var(--gap);
		justify-items: start;
		margin-bottom: 1rem;
	}

	.items {
		list-style: none;
		margin: 0;
		padding: 0;
	}
</style>
