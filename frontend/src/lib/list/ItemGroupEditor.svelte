<script lang="ts">
	import type { ActionResult, ItemGroup, RoomHandle } from '#lib/data/index.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import { trimItemName } from '#lib/data/overlay.ts';
	import { MAX_NAME_LENGTH } from '#lib/ui/field-limits.ts';
	import { untrack } from 'svelte';

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
	const itemsId = `${formId}-items`;
	let name = $state(untrack(() => group?.name ?? ''));
	let itemsText = $state(untrack(() => group?.items.join('\n') ?? ''));
	let error = $state('');
	let conflict = $state(false);
	let replaceNewer = $state(false);
	let baseSeq = $state(untrack(() => group?.changed_seq ?? 0));
	const latest = $derived(group ? getLatest?.() : undefined);

	async function save() {
		error = '';
		const items = itemsText
			.split(/\r?\n/)
			.map(trimItemName)
			.filter((item) => item.length > 0);
		const result = await onSave(name, items, group ? baseSeq : null);
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
	<label for={itemsId}>Item names, one per line</label>
	<textarea id={itemsId} bind:value={itemsText} rows="8" spellcheck="false"></textarea>
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
	<p class="hint">
		Blank lines are ignored. Groups may be empty and can contain up to 1,000 different items.
	</p>
</FormDialog>

<style>
	textarea {
		min-height: 10rem;
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
