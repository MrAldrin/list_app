<script lang="ts">
	import type { ItemGroup, List, RoomHandle } from '#lib/data/index.ts';
	import ConfirmDialog from '#lib/ui/ConfirmDialog.svelte';
	import Dialog from '#lib/ui/Dialog.svelte';
	import NeedsConnection from '#lib/ui/NeedsConnection.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import ItemGroupEditor from './ItemGroupEditor.svelte';

	let { room, list }: { room: RoomHandle; list: List } = $props();
	const online = $derived(room.store.canWrite);
	const hintId = $props.id();
	let managing = $state(false);
	let editor = $state<{ group: ItemGroup | null } | null>(null);
	let deleting = $state.raw<ItemGroup | null>(null);

	async function add(group: ItemGroup) {
		const result = await room.addItemGroup(list, group);
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			return;
		}
		const { added, skipped, queued, failures } = result.result;
		const parts: string[] = [];
		if (added) parts.push(`Added ${added}`);
		if (skipped) parts.push(`skipped ${skipped} already on the list`);
		if (queued) parts.push(`queued ${queued} for sync`);
		if (failures.length) parts.push(`${failures.length} could not be added`);
		const summary = parts.join('; ') || 'No items to add';
		const failedNames = failures
			.slice(0, 3)
			.map((failure) => `'${failure.name}'`)
			.join(', ');
		const remainingFailures = failures.length > 3 ? ` and ${failures.length - 3} more` : '';
		const detail = failures.length
			? `: ${failedNames}${remainingFailures} (${failures[0].message})`
			: '';
		const kind = failures.length ? 'warning' : queued ? 'info' : added ? 'success' : 'info';
		toasts.show(`${summary}${detail}`, kind);
	}

	function create() {
		managing = false;
		editor = { group: null };
	}

	function edit(group: ItemGroup) {
		managing = false;
		editor = { group };
	}

	async function saveGroup(name: string, items: string[], baseSeq: number | null) {
		if (editor?.group) {
			const result = await room.updateItemGroup(
				{ ...editor.group, changed_seq: baseSeq ?? editor.group.changed_seq },
				name,
				items
			);
			if (result.ok) toasts.show('Item group saved', 'success');
			return result;
		}
		const result = await room.createItemGroup(name, items);
		if (result.ok) toasts.show('Item group saved', 'success');
		return result;
	}

	async function confirmDelete() {
		if (!deleting) return;
		const target = room.store.itemGroup(deleting.uid) ?? deleting;
		const result = await room.deleteItemGroup(target);
		if (result.ok) {
			toasts.show(`Deleted '${target.name}'`, 'danger');
			deleting = null;
			return;
		}
		toasts.show(result.message, 'warning');
		if (result.code === 'group_changed_meanwhile') {
			deleting = room.store.itemGroup(target.uid) ?? null;
		} else if (result.code === 'group_unavailable') deleting = null;
	}
</script>

<section class="item-groups" aria-label="Item groups">
	{#if room.store.groups.length > 0}
		<p class="label">Item groups</p>
		<div class="group-buttons">
			{#each room.store.groups as group (group.uid)}
				<button
					class="outline group-add"
					type="button"
					disabled={!room.store.canEdit}
					aria-label={group.items.length === 0 ? `${group.name}, empty group` : undefined}
					title={group.items.length === 0 ? 'Empty group. Edit it to add items.' : undefined}
					onclick={() => add(group)}
				>
					{group.name}
				</button>
			{/each}
		</div>
	{/if}
	<button
		class="manage"
		type="button"
		disabled={!online}
		title={online ? undefined : 'Needs a connection'}
		aria-describedby={online ? undefined : hintId}
		onclick={() => (managing = true)}
	>
		{room.store.groups.length ? 'Manage groups' : 'Create an item group'}
	</button>
	<NeedsConnection id={hintId} show={!online} />
</section>

{#if managing}
	<Dialog title="Item groups" onClose={() => (managing = false)}>
		{#if room.store.groups.length === 0}
			<p class="empty">No groups yet. Save item names for a quick add.</p>
		{:else}
			<ul class="manage-list">
				{#each room.store.groups as group (group.uid)}
					<li>
						<div class="group-info">
							<strong>{group.name}</strong>
							{#if group.items.length === 0}
								<span>Empty group</span>
							{:else}
								<span>{group.items.length} {group.items.length === 1 ? 'item' : 'items'}</span>
							{/if}
						</div>
						<button type="button" class="outline" disabled={!online} onclick={() => edit(group)}
							>Edit</button
						>
						<button
							type="button"
							class="outline danger"
							disabled={!online}
							onclick={() => (deleting = group)}
						>
							Delete
						</button>
					</li>
				{/each}
			</ul>
		{/if}
		<div class="actions">
			<button type="button" onclick={() => (managing = false)}>Close</button>
			<button class="primary" type="button" disabled={!online} onclick={create}>New group</button>
		</div>
	</Dialog>
{/if}

{#if editor}
	{@const group = editor.group}
	<ItemGroupEditor
		{room}
		{group}
		getLatest={() => (group ? room.store.itemGroup(group.uid) : undefined)}
		onSave={saveGroup}
		onClose={() => (editor = null)}
	/>
{/if}

{#if deleting}
	<ConfirmDialog
		question="Delete '{deleting.name}'?"
		detail="This removes the group from the room. Items already added to lists stay there."
		confirmLabel="Delete group"
		confirmDisabled={!online}
		onConfirm={confirmDelete}
		onClose={() => (deleting = null)}
	/>
{/if}

<style>
	.item-groups {
		display: grid;
		gap: 0.25rem;
		padding: 0.25rem 0 0.5rem;
	}

	.label {
		color: var(--text-muted);
		font-size: 0.9rem;
	}

	.group-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}

	.group-add {
		min-height: 40px;
		padding: 0 0.75rem;
		text-align: left;
		overflow-wrap: anywhere;
	}

	.manage {
		justify-self: start;
		min-height: 36px;
		padding: 0 0.5rem;
		color: var(--text-muted);
		font-size: 0.9rem;
	}

	.empty {
		margin-bottom: 0.75rem;
		color: var(--text-muted);
	}

	.manage-list {
		list-style: none;
		padding: 0;
		margin: 0 0 1rem;
		display: grid;
		gap: 0.5rem;
	}

	.manage-list li {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-width: 0;
	}

	.group-info {
		flex: 1;
		min-width: 0;
		display: grid;
	}

	.group-info strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.group-info span {
		color: var(--text-muted);
		font-size: 0.85rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
