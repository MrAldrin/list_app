<!--
	"Edit Tag": the name (a rename, saved with Save), the color (a dot per
	palette color, saved at once) and "Delete tag". The parent deletes the tag
	with the undo toast and renames it.
-->
<script lang="ts">
	import { MAX_TAG_LENGTH } from '#lib/ui/field-limits.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import { untrack } from 'svelte';
	import { colorVar, TAG_COLOR_COUNT } from './tags';

	let {
		tag,
		colorIndex,
		canEdit,
		onColor,
		onRename,
		onDelete,
		onClose
	}: {
		tag: string;
		/** The palette index (0 to 6) the tag has now. */
		colorIndex: number;
		/** Whether the tag may be changed (shared-data writes are authorized). */
		canEdit: boolean;
		onColor: (index: number) => void;
		/** Renames the tag; true when the card should close. */
		onRename: (name: string) => Promise<boolean>;
		onDelete: () => void;
		onClose: () => void;
	} = $props();

	const palette = Array.from({ length: TAG_COLOR_COUNT }, (_, index) => index);
	const nameId = $props.id();
	// `untrack`: start with the name at opening; the field keeps what is typed.
	let name = $state(untrack(() => tag));

	async function submit() {
		if (await onRename(name)) onClose();
	}
</script>

<FormDialog
	title="Edit Tag"
	submitLabel="Save"
	submitDisabled={!canEdit}
	focusBox
	onSubmit={submit}
	{onClose}
>
	<label for={nameId}>Tag Name</label>
	<input
		id={nameId}
		bind:value={name}
		maxlength={MAX_TAG_LENGTH}
		autocomplete="off"
		enterkeyhint="done"
		disabled={!canEdit}
	/>
	<span class="label">Color</span>
	<div class="colors" role="group" aria-label="Color of {tag}">
		{#each palette as index (index)}
			<button
				class="color"
				type="button"
				aria-label="Color {index + 1}"
				aria-pressed={colorIndex === index}
				disabled={!canEdit}
				style:--tag={colorVar(index)}
				onclick={() => onColor(index)}
			>
				<span class="dot"></span>
			</button>
		{/each}
	</div>
	{#snippet leading()}
		<button class="delete" type="button" disabled={!canEdit} onclick={onDelete}>Delete tag</button>
		<span class="spacer"></span>
	{/snippet}
</FormDialog>

<style>
	.label {
		display: block;
		font-weight: 600;
	}

	.colors {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin: 0.25rem 0 0.75rem;
	}

	/* A 44px tap area; the dot is what shows. */
	.color {
		width: var(--touch);
		height: var(--touch);
		min-height: 0;
		padding: 0;
		display: grid;
		place-items: center;
		border: none;
		background: transparent;
	}

	.dot {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: var(--tag);
	}

	/* A ring around the chosen color. */
	.color[aria-pressed='true'] .dot {
		box-shadow:
			0 0 0 2px var(--surface),
			0 0 0 4px var(--text);
	}

	.delete {
		min-height: var(--touch);
		padding: 0 0.5rem;
		color: var(--danger);
	}

	.spacer {
		flex: 1;
	}
</style>
