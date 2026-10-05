<!--
	The list itself: header, options, tags, the add field and the items, with
	every edit. The room's list page and the share-link page both show it; on a
	share link there is no way back to the room and no "Reset share link".
-->
<script lang="ts">
	import type { HideDone, Item, List, RoomHandle } from '#lib/data/index.ts';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import AddItem from './AddItem.svelte';
	import ItemDialog from './ItemDialog.svelte';
	import ItemRow from './ItemRow.svelte';
	import ListHeader from './ListHeader.svelte';
	import ListMenu from './ListMenu.svelte';
	import ListOptions from './ListOptions.svelte';
	import ListTags from './ListTags.svelte';
	import { addFeedback, loadShowQuantities, saveShowQuantities, UNDO_DURATION } from './items.ts';
	import { activeFilter, filterByTag } from './tags.ts';

	let {
		room,
		list,
		roomHref,
		canReset
	}: {
		room: RoomHandle;
		list: List;
		/** The back link; null on a share link. */
		roomHref: string | null;
		/** Room members may reset the share link. */
		canReset: boolean;
	} = $props();

	let optionsOpen = $state(false);
	// "Show quantities": personal, saved per list in this browser.
	// A writable `$derived`: read again when the list changes, set by the switch.
	const listUid = $derived(list.uid);
	let showQuantities = $derived(loadShowQuantities(listUid));
	function setShowQuantities(on: boolean) {
		showQuantities = on;
		saveShowQuantities(listUid, on);
	}
	/** The item in the edit dialog, as it was when the dialog opened. */
	let editing = $state.raw<Item | null>(null);
	/** The tag chip the items are filtered by (page state, as in NiceGUI). */
	let chosenTag = $state<string | null>(null);
	const filterTag = $derived(activeFilter(chosenTag, list.tags));

	// "Hide after N days" depends on the clock, so the visible items are
	// worked out again every minute (NiceGUI does the same).
	let now = $state(new Date());
	$effect(() => {
		const timer = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(timer);
	});

	async function addItem(target: List, name: string): Promise<boolean> {
		const result = await room.addItem(target, name);
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
		void room.setDone(item, done);
	}

	function changeQuantity(item: Item, delta: number) {
		void room.changeQuantity(item, delta);
	}

	function toggleTag(item: Item, tag: string) {
		void room.toggleItemTag(item, tag);
	}

	async function addTag(target: List, tag: string): Promise<boolean> {
		// The chip shows at once; a rejection is shown by the store as a toast.
		const result = await room.addListTag(target, tag);
		return result.ok;
	}

	/** Deletes at once and offers "Undo" for a few seconds, like item deletes. */
	function deleteTag(target: List, tag: string) {
		if (chosenTag === tag) chosenTag = null;
		const handle = room;
		const deleted = handle.removeListTag(target, tag);
		const toastId = toasts.show(`Deleted tag ${tag}`, 'danger', {
			duration: UNDO_DURATION,
			action: { label: 'Undo', run: () => void undoDeleteTag(handle, target, tag) }
		});
		void deleted.then((result) => {
			if (!result.ok) toasts.dismiss(toastId);
		});
	}

	async function undoDeleteTag(handle: RoomHandle, target: List, tag: string) {
		const result = await handle.addListTag(target, tag);
		if (result.ok) toasts.show(`Restored tag ${tag}`, 'success');
	}

	function setHideDone(target: List, changes: Partial<HideDone>) {
		void room.setVisibility(target, changes);
	}

	async function saveItem(
		item: Item,
		changes: { name: string; description: string; quantity: number }
	) {
		const result = await room.editItem(item, changes);
		// A blank or duplicate name keeps the dialog open to fix it (the store
		// shows why). It closes when the item or the list is gone.
		if (result.ok || result.code === 'item_not_found' || result.code === 'list_unavailable') {
			editing = null;
		}
	}

	/** Deletes at once and offers "Undo" for a few seconds. */
	function deleteItem(item: Item) {
		editing = null;
		const handle = room;
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

<ListHeader
	name={list.name}
	{roomHref}
	{optionsOpen}
	onToggleOptions={() => (optionsOpen = !optionsOpen)}
>
	{#snippet menu()}
		<ListMenu {room} {list} {canReset} />
	{/snippet}
</ListHeader>
{#if room.store.error}
	<!-- The items below may be out of date; they stay usable. -->
	<LoadError
		title="Could not load the latest changes."
		detail={room.store.error}
		onRetry={() => room.store.refresh()}
	/>
{/if}
{#if optionsOpen}
	<ListOptions
		bind:showQuantities={() => showQuantities, setShowQuantities}
		hideDone={list.hide_done}
		onHideDone={(changes) => setHideDone(list, changes)}
	/>
{/if}
<ListTags
	tags={list.tags}
	filter={filterTag}
	editing={optionsOpen}
	onFilter={(tag) => (chosenTag = tag)}
	onAdd={(tag) => addTag(list, tag)}
	onDelete={(tag) => deleteTag(list, tag)}
/>
<AddItem items={room.store.itemsOf(list.uid)} onAdd={(name) => addItem(list, name)} />
<ul class="items">
	<!-- Hide checked items first (on the whole list), then filter by tag. -->
	{#each filterByTag(room.store.visibleItemsOf(list.uid, now), filterTag) as item (item.uid)}
		<ItemRow
			{item}
			showQuantity={showQuantities}
			showDelete={optionsOpen}
			listTags={list.tags}
			onToggle={(done) => toggle(item, done)}
			onQuantity={(delta) => changeQuantity(item, delta)}
			onTag={(tag) => toggleTag(item, tag)}
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

<style>
	.items {
		list-style: none;
		margin: 0;
		padding: 0;
	}
</style>
