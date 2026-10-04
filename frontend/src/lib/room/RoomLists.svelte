<!--
	The lists of a room, with "Add New List", rename and delete. Texts match
	the NiceGUI room page. Rejected changes (such as a duplicate name) come
	back as `store.notice`; the room page shows those as toasts.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { List, RoomHandle } from '#lib/data/index.ts';
	import ConfirmDialog from '#lib/ui/ConfirmDialog.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import NameDialog from '#lib/ui/NameDialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let { room }: { room: RoomHandle } = $props();

	// Which dialog is open. `$state.raw` stores the list object as it is,
	// without making it deeply reactive (we never change it in place).
	let creating = $state(false);
	let renaming = $state.raw<List | null>(null);
	let deleting = $state.raw<List | null>(null);

	async function createList(name: string) {
		const result = await room.createList(name);
		if (!result.ok) return; // The store shows why, as a toast.
		creating = false;
		// An existing name (ignoring case) gives the existing list, like NiceGUI.
		if (result.result.created) toasts.show('List created', 'success');
		await goto(resolve('/room/[slug]/list/[list]', { slug: room.slug, list: result.result.slug }));
	}

	async function renameList(list: List, name: string) {
		const result = await room.renameList(list, name);
		if (!result.ok) {
			// Keep the dialog open to fix the name, unless the list is gone.
			if (result.code === 'list_unavailable') renaming = null;
			return;
		}
		renaming = null;
		toasts.show(`Updated ${room.store.list(list.uid)?.name ?? name.trim()}`, 'success');
	}

	async function deleteList(list: List) {
		const result = await room.deleteList(list);
		deleting = null;
		if (result.ok) toasts.show(`Deleted '${list.name}'`, 'danger');
	}
</script>

<button class="outline add" type="button" onclick={() => (creating = true)}>
	<Icon name="add" />
	Add New List
</button>

{#if room.store.lists.length === 0}
	<p class="muted empty">No lists yet. Create your first one!</p>
{:else}
	<ul>
		<!-- `(list.uid)` is the key: Svelte uses it to match rows when the order changes. -->
		{#each room.store.lists as list (list.uid)}
			<li class="card">
				<a href={resolve('/room/[slug]/list/[list]', { slug: room.slug, list: list.slug })}
					><span>{list.name}</span></a
				>
				<button
					class="icon"
					type="button"
					aria-label="Rename {list.name}"
					onclick={() => (renaming = list)}
				>
					<Icon name="edit" />
				</button>
				<button
					class="icon delete"
					type="button"
					aria-label="Delete {list.name}"
					onclick={() => (deleting = list)}
				>
					<Icon name="delete" />
				</button>
			</li>
		{/each}
	</ul>
{/if}

{#if creating}
	<NameDialog
		title="New List"
		label="List name"
		onSave={createList}
		onClose={() => (creating = false)}
	/>
{/if}

{#if renaming}
	{@const list = renaming}
	<NameDialog
		title="Edit '{list.name}'"
		label="List Name"
		initial={list.name}
		onSave={(name) => renameList(list, name)}
		onClose={() => (renaming = null)}
	/>
{/if}

{#if deleting}
	{@const list = deleting}
	<ConfirmDialog
		question="Delete '{list.name}' and its {room.store.itemsOf(list.uid).length} items?"
		confirmLabel="Delete"
		onConfirm={() => deleteList(list)}
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

	/* Long names stay on one line and end with "…". */
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

	.icon.delete {
		color: var(--danger);
	}
</style>
