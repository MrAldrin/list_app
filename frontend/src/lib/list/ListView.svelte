<!--
	The list itself: header, options, tags, the add field and the items, with
	every edit. The room's list page and the share-link page both show it; a
	share link shows the way back to the room and "Reset share link" only to
	browsers that have access to the room.
-->
<script lang="ts">
	import {
		countHiddenChecked,
		itemSortChoice,
		type HideDone,
		type Item,
		type List,
		type RoomHandle,
		sortItems
	} from '#lib/data/index.ts';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { showUndoToast } from '#lib/ui/undo-toast.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import AddItem from './AddItem.svelte';
	import ItemDialog from './ItemDialog.svelte';
	import ItemRow from './ItemRow.svelte';
	import ListHeader from './ListHeader.svelte';
	import ListMenu from './ListMenu.svelte';
	import ListOptions from './ListOptions.svelte';
	import ListTags from './ListTags.svelte';
	import {
		addFeedback,
		checkFeedback,
		loadItemSort,
		loadShowQuantities,
		saveItemSort,
		saveShowQuantities,
		UNDO_DURATION
	} from './items.ts';
	import { searchItems } from './search.ts';
	import { activeFilters, filterByTags } from './tags.ts';

	let {
		room,
		list,
		roomHref,
		canReset,
		onReset
	}: {
		room: RoomHandle;
		list: List;
		/** The back link; null on a share link without room access. */
		roomHref: string | null;
		/** Room members may reset the share link. */
		canReset: boolean;
		/** Called with the new share token after a reset. */
		onReset?: (token: string) => void;
	} = $props();

	// Edits may start offline (they are queued). Sharing and resets need the server.
	const canEdit = $derived(room.store.canEdit);
	const online = $derived(room.store.canWrite);
	let optionsOpen = $state(false);
	let searchText = $state('');
	// "Show quantities": personal, saved per list in this browser.
	// A writable `$derived`: read again when the list changes, set by the switch.
	const listUid = $derived(list.uid);
	let showQuantities = $derived(loadShowQuantities(listUid));
	function setShowQuantities(on: boolean) {
		showQuantities = on;
		saveShowQuantities(listUid, on);
	}
	// "Sort": personal too, saved per list in this browser (name A–Z by default).
	let itemSort = $derived(loadItemSort(listUid));
	function setItemSort(choiceId: string) {
		const choice = itemSortChoice(choiceId);
		if (!choice) return;
		itemSort = choice;
		saveItemSort(listUid, choice.id);
	}
	/** The item in the edit dialog, as it was when the dialog opened. */
	let editing = $state.raw<Item | null>(null);
	/** The tag chips the items are filtered by, all must match (page state, as in NiceGUI). */
	let chosenTags = $state<string[]>([]);
	const filterTags = $derived(activeFilters(chosenTags, list.tags));
	const visibleItems = $derived.by(() => {
		// Typing filters the list only for a saved or unconfirmed view; online it
		// only suggests (also while access is briefly being revalidated).
		const searching = room.store.unconfirmedView && searchText.trim() !== '';
		const items = searching
			? searchItems(room.store.itemsOf(list.uid), searchText)
			: room.store.visibleItemsOf(list.uid, now);
		// Sorted last, after the search and the tag filter (open items still first).
		return sortItems(filterByTags(items, filterTags), itemSort);
	});

	// "Hide after N days" depends on the clock, so the visible items are
	// worked out again every minute (NiceGUI does the same).
	let now = $state(new Date());
	$effect(() => {
		const timer = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(timer);
	});
	// Checked items the hide-done rule hides (not search or tag filters).
	const hiddenChecked = $derived(
		countHiddenChecked(room.store.itemsOf(list.uid), list.hide_done, now)
	);
	const hiddenText = $derived(
		`${hiddenChecked} ${hiddenChecked === 1 ? 'checked item' : 'checked items'} hidden`
	);

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

	/**
	 * Checks or unchecks at once and says which item, with "Undo": when
	 * someone else changes the list at the same moment, a tap can land on
	 * the wrong item.
	 */
	function toggle(item: Item, done: boolean) {
		const handle = room;
		showUndoToast({
			...checkFeedback(item.name, done),
			request: handle.setDone(item, done),
			duration: UNDO_DURATION,
			canUndo: () => handle.store.canEdit,
			undo: () => undoToggle(handle, item, done)
		});
	}

	/** Sets the item back, unless it is gone or already back (someone else). */
	function undoToggle(handle: RoomHandle, item: Item, done: boolean) {
		const current = handle.store.itemsOf(item.list_uid).find((i) => i.uid === item.uid);
		if (current && current.done === done) void handle.setDone(current, !done);
	}

	function changeQuantity(item: Item, delta: number) {
		void room.changeQuantity(item, delta);
	}

	function toggleTag(item: Item, tag: string) {
		void room.toggleItemTag(item, tag);
	}

	/** Adds the tag to the filter, or removes it when it is already there. */
	function toggleFilter(tag: string) {
		chosenTags = chosenTags.includes(tag)
			? chosenTags.filter((chosen) => chosen !== tag)
			: [...chosenTags, tag];
	}

	async function addTag(target: List, tag: string): Promise<boolean> {
		// The chip shows at once; a rejection is shown by the store as a toast.
		const result = await room.addListTag(target, tag);
		return result.ok;
	}

	/** Deletes at once and offers "Undo" for a few seconds, like item deletes. */
	function deleteTag(target: List, tag: string) {
		chosenTags = chosenTags.filter((chosen) => chosen !== tag);
		const handle = room;
		showUndoToast({
			message: `Deleted tag ${tag}`,
			request: handle.removeListTag(target, tag),
			duration: UNDO_DURATION,
			canUndo: () => handle.store.canEdit,
			undo: () => undoDeleteTag(handle, target, tag)
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
		changes: { name: string; description: string; quantity: number; date: string | null }
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
		showUndoToast({
			message: `Deleted ${item.name}`,
			request: handle.deleteItem(item),
			duration: UNDO_DURATION,
			canUndo: () => handle.store.canEdit,
			undo: () => undoDelete(handle, item)
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
		<ListMenu {room} {list} canReset={canReset && online} {onReset} />
	{/snippet}
</ListHeader>
{#if room.store.error && !(room.store.showsOfflineNotice && room.store.unreachable)}
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
		sort={itemSort}
		onSort={setItemSort}
		hideDone={list.hide_done}
		{canEdit}
		onHideDone={(changes) => setHideDone(list, changes)}
	/>
{/if}
<ListTags
	tags={list.tags}
	filter={filterTags}
	editing={optionsOpen}
	{canEdit}
	onToggleFilter={toggleFilter}
	onAdd={(tag) => addTag(list, tag)}
	onDelete={(tag) => deleteTag(list, tag)}
/>
<AddItem
	items={room.store.itemsOf(list.uid)}
	{canEdit}
	bind:text={searchText}
	onAdd={(name) => addItem(list, name)}
/>
<ul class="items">
	<!-- Hide checked items first (on the whole list), then filter by tag. -->
	{#each visibleItems as item (item.uid)}
		<ItemRow
			{item}
			showQuantity={showQuantities}
			showDelete={optionsOpen}
			{canEdit}
			listTags={list.tags}
			unsent={room.store.isUnsent(`item:${item.uid}`)}
			onToggle={(done) => toggle(item, done)}
			onQuantity={(delta) => changeQuantity(item, delta)}
			onTag={(tag) => toggleTag(item, tag)}
			onOpen={() => (editing = item)}
			onDelete={() => deleteItem(item)}
		/>
	{/each}
</ul>
{#if hiddenChecked > 0}
	<p class="hidden-count">{hiddenText}</p>
{/if}
{#if filterTags.length > 0 && visibleItems.length === 0}
	<p class="hidden-count">No items match all selected tags.</p>
{/if}
{#if editing}
	{@const item = editing}
	<ItemDialog
		{item}
		{canEdit}
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

	.hidden-count {
		margin: var(--gap) 0 0;
		text-align: center;
		color: var(--text-muted);
	}
</style>
