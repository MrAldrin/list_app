<script lang="ts">
	import type { ActionResult, ItemGroup, RoomHandle } from '#lib/data/index.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import { itemNameKey, trimItemName } from '#lib/data/overlay.ts';
	import { MAX_NAME_LENGTH } from '#lib/ui/field-limits.ts';
	import { keepFocus } from '#lib/ui/focus.ts';
	import { untrack } from 'svelte';
	import { itemGroupSuggestions, MAX_GROUP_ITEM_COUNT } from './item-group-items.ts';

	let {
		room,
		group = null,
		getLatest,
		onSave,
		onClose
	}: {
		room: RoomHandle;
		group?: ItemGroup | null;
		getLatest?: () => ItemGroup | undefined;
		onSave: (
			name: string,
			items: string[],
			baseSeq: number | null
		) => Promise<ActionResult<ItemGroup>>;
		onClose: () => void;
	} = $props();

	const formId = $props.id();
	const nameId = `${formId}-name`;
	const itemId = `${formId}-item`;
	const suggestionListId = `${formId}-suggestions`;
	let name = $state(untrack(() => group?.name ?? ''));
	let items = $state<string[]>(untrack(() => [...(group?.items ?? [])]));
	let itemText = $state('');
	let itemInput = $state<HTMLInputElement>();
	let itemError = $state('');
	let suggestionsOpen = $state(false);
	let suggestionsFocused = $state(false);
	let activeName = $state<string | null>(null);
	let error = $state('');
	let conflict = $state(false);
	let replaceNewer = $state(false);
	let baseSeq = $state(untrack(() => group?.changed_seq ?? 0));
	const latest = $derived(group ? getLatest?.() : undefined);

	// This reads only lists and items already in this room's live or saved view.
	const roomItemNames = $derived(
		room.store.lists.flatMap((list) => room.store.itemsOf(list.uid).map((item) => item.name))
	);
	const shown = $derived(
		suggestionsOpen && suggestionsFocused
			? itemGroupSuggestions(roomItemNames, items, itemText)
			: []
	);
	const active = $derived(activeName === null ? -1 : shown.indexOf(activeName));

	$effect(() => {
		if (activeName !== null && !shown.includes(activeName)) activeName = null;
	});

	function typed() {
		activeName = null;
		suggestionsOpen = true;
		itemError = '';
	}

	function addItem(raw: string) {
		const item = trimItemName(raw);
		if (!item) return;
		if (items.some((current) => itemNameKey(current) === itemNameKey(item))) {
			itemError = `'${item}' is already in this group.`;
			return;
		}
		if (items.length >= MAX_GROUP_ITEM_COUNT) {
			itemError = `Groups can have up to ${MAX_GROUP_ITEM_COUNT} items.`;
			return;
		}
		items = [...items, item];
		itemText = '';
		itemError = '';
		activeName = null;
		suggestionsOpen = true;
		itemInput?.focus();
	}

	function removeItem(item: string) {
		items = items.filter((current) => current !== item);
		itemError = '';
	}

	function keydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown' && shown.length > 0) {
			event.preventDefault();
			activeName = shown[(active + 1) % shown.length];
		} else if (event.key === 'ArrowUp' && shown.length > 0) {
			event.preventDefault();
			activeName = shown[active <= 0 ? shown.length - 1 : active - 1];
		} else if (event.key === 'Escape' && shown.length > 0) {
			event.preventDefault();
			suggestionsOpen = false;
			activeName = null;
		} else if (event.key === 'Enter') {
			event.preventDefault();
			event.stopPropagation();
			addItem(active >= 0 && shown[active] ? shown[active] : itemText);
		}
	}

	async function save() {
		error = '';
		const result = await onSave(name, [...items], group ? baseSeq : null);
		if (result.ok) {
			onClose();
			return;
		}
		error = result.message;
		if (result.code !== 'group_changed_meanwhile' || !group) return;
		const current = getLatest?.();
		if (!current) return;
		error = '';
		baseSeq = current.changed_seq;
		conflict = true;
		replaceNewer = false;
	}
</script>

<FormDialog
	title={group ? `Edit '${group.name}'` : 'New item group'}
	submitLabel={conflict ? 'Save my draft' : 'Save'}
	submitDisabled={!room.store.canWrite || (conflict && !replaceNewer)}
	onSubmit={save}
	{onClose}
>
	<label for={nameId}>Group name</label>
	<input id={nameId} bind:value={name} maxlength={MAX_NAME_LENGTH} autocomplete="off" />
	<label for={itemId}>Add item name</label>
	<div class="item-entry">
		<input
			bind:this={itemInput}
			id={itemId}
			bind:value={itemText}
			maxlength={MAX_NAME_LENGTH}
			oninput={typed}
			onkeydown={keydown}
			onfocus={() => (suggestionsFocused = true)}
			onblur={() => {
				suggestionsFocused = false;
				activeName = null;
			}}
			role="combobox"
			aria-autocomplete="list"
			aria-expanded={shown.length > 0}
			aria-controls={shown.length > 0 ? suggestionListId : undefined}
			aria-activedescendant={active >= 0 ? `${suggestionListId}-${active}` : undefined}
			autocomplete="off"
			spellcheck="false"
		/>
		<button
			class="outline"
			type="button"
			disabled={!trimItemName(itemText) || items.length >= MAX_GROUP_ITEM_COUNT}
			onclick={() => addItem(itemText)}
		>
			Add item
		</button>
		{#if shown.length > 0}
			<ul
				id={suggestionListId}
				class="suggestions"
				role="listbox"
				aria-label="Existing items in this room"
			>
				{#each shown as suggestion, index (suggestion)}
					<!-- The combobox keeps focus while an option is selected. -->
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<li
						id="{suggestionListId}-{index}"
						class:active={index === active}
						role="option"
						aria-selected={index === active}
						onmousedown={keepFocus}
						onclick={() => addItem(suggestion)}
					>
						{suggestion}
					</li>
				{/each}
			</ul>
		{/if}
	</div>
	{#if itemError}<p class="item-error" role="status">{itemError}</p>{/if}
	<p class="hint">
		Type a new name or choose an existing item from any list in this room. Names can appear once;
		groups may be empty and contain up to {MAX_GROUP_ITEM_COUNT} items.
	</p>
	{#if items.length > 0}
		<p class="items-label">Items in group</p>
		<ul class="group-items" aria-label="Items in group">
			{#each items as item (item)}
				<li>
					<span>{item}</span>
					<button
						class="outline"
						type="button"
						aria-label="Remove {item}"
						onclick={() => removeItem(item)}
					>
						Remove
					</button>
				</li>
			{/each}
		</ul>
	{/if}
	{#if conflict}
		<p class="conflict" role="alert">
			Someone else changed this group. Your draft is still here. The latest saved version is
			{latest?.name ?? 'unavailable'} ({latest?.items.length ?? 0}
			{latest?.items.length === 1 ? 'item' : 'items'}).
		</p>
		<label class="overwrite">
			<input type="checkbox" bind:checked={replaceNewer} />
			Save my draft over the latest version
		</label>
	{/if}
	{#if error}<p class="error" role="alert">{error}</p>{/if}
</FormDialog>

<style>
	.item-entry {
		position: relative;
		display: flex;
		gap: 0.5rem;
	}

	.item-entry input {
		min-width: 0;
		flex: 1;
	}

	.item-entry > button {
		flex: 0 0 auto;
		padding: 0 0.75rem;
	}

	.suggestions {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		z-index: 1;
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0.25rem 0;
		background: var(--surface);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
	}

	.suggestions li {
		min-height: var(--touch);
		padding: 0.6rem 0.75rem;
		overflow-wrap: anywhere;
		cursor: pointer;
	}

	.suggestions li.active {
		background: var(--border);
	}

	.items-label {
		font-weight: 600;
	}

	.group-items {
		list-style: none;
		padding: 0;
		margin: 0;
		display: grid;
		gap: 0.25rem;
	}

	.group-items li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		min-width: 0;
	}

	.group-items li span {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.group-items button {
		flex: 0 0 auto;
		padding: 0 0.65rem;
	}

	.item-error {
		color: var(--danger);
	}

	.conflict {
		padding: 0.5rem;
		border-radius: var(--radius);
		background: var(--border);
		overflow-wrap: anywhere;
	}

	.overwrite {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.overwrite input {
		width: auto;
		min-height: 0;
	}

	.hint {
		color: var(--text-muted);
		font-size: 0.9rem;
	}
</style>
