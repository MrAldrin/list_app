<!--
	"Tags" in Options: how an item takes tags ("One tag per item" or "Several
	tags per item"), whether the rows show the tag letters, then adding and
	deleting the list's tags. The settings are saved for the list, for everyone;
	each change is sent at once.
-->
<script lang="ts">
	import type { Item, TagMode, TagSettings } from '#lib/data/index.ts';
	import ConfirmDialog from '#lib/ui/ConfirmDialog.svelte';
	import Dialog from '#lib/ui/Dialog.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import { keepFocus } from '#lib/ui/focus.ts';
	import { MAX_TAG_LENGTH } from '#lib/ui/field-limits.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import {
		colorVar,
		countSeveralTags,
		newTag,
		severalTagsQuestion,
		TAG_COLOR_COUNT,
		tagColor,
		tagColorIndex
	} from './tags';

	const colorIndexes = Array.from({ length: TAG_COLOR_COUNT }, (_, index) => index);

	let {
		tags,
		settings,
		items,
		canEdit,
		onSettings,
		onColor,
		onAdd,
		onDelete,
		onClose
	}: {
		/** The list's tags, sorted ignoring case. */
		tags: readonly string[];
		settings: TagSettings;
		/** All list items, to count those with several tags before a switch to one tag per item. */
		items: readonly Item[];
		/** Whether shared-data tag mutations are authorized. */
		canEdit: boolean;
		/** Saves a changed setting (mode, show on items, only item tags). */
		onSettings: (changes: {
			mode?: TagMode;
			show_on_items?: boolean;
			only_item_tags?: boolean;
		}) => void;
		onColor: (tag: string, index: number) => void;
		/** Adds a tag; true when the field should be cleared. */
		onAdd: (tag: string) => Promise<boolean>;
		onDelete: (tag: string) => void;
		onClose: () => void;
	} = $props();

	let text = $state('');
	let input = $state<HTMLInputElement>();
	/** The tag whose color choices are open, if any. */
	let coloring = $state<string | null>(null);
	let confirming = $state(false);
	const several = $derived(countSeveralTags(items));

	function chooseMode(mode: TagMode) {
		if (mode === settings.mode) return;
		if (mode === 'multi' || several === 0) {
			onSettings({ mode });
		} else {
			confirming = true;
		}
	}

	async function confirmSingle() {
		confirming = false;
		onSettings({ mode: 'single' });
	}

	function chooseColor(tag: string, index: number) {
		coloring = null;
		onColor(tag, index);
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!canEdit) return;
		const tag = newTag(text, tags);
		if (tag === null) {
			// Exact match only: "fruit" next to "Fruit" is allowed.
			const name = text.trim();
			if (name) {
				toasts.show(`'${name}' is already a tag`, 'warning');
				text = '';
			}
			return;
		}
		const sent = text;
		input?.focus();
		const clear = await onAdd(tag);
		if (clear && text === sent) text = '';
	}
</script>

<Dialog title="Tags" {onClose}>
	<div class="segmented" role="group" aria-label="Tags per item">
		<button
			type="button"
			aria-pressed={settings.mode === 'single'}
			class:on={settings.mode === 'single'}
			disabled={!canEdit}
			onclick={() => chooseMode('single')}>One tag per item</button
		>
		<button
			type="button"
			aria-pressed={settings.mode === 'multi'}
			class:on={settings.mode === 'multi'}
			disabled={!canEdit}
			onclick={() => chooseMode('multi')}>Several tags per item</button
		>
	</div>
	<label class="switch">
		<span>Show tags on items</span>
		<input
			type="checkbox"
			role="switch"
			checked={settings.show_on_items}
			disabled={!canEdit}
			onchange={(event) => onSettings({ show_on_items: event.currentTarget.checked })}
		/>
	</label>
	<label class="switch sub" class:disabled={!settings.show_on_items}>
		<span>Only show tags the item has</span>
		<input
			type="checkbox"
			role="switch"
			checked={settings.only_item_tags}
			disabled={!canEdit || !settings.show_on_items}
			onchange={(event) => onSettings({ only_item_tags: event.currentTarget.checked })}
		/>
	</label>

	<form class="add" onsubmit={submit} novalidate>
		<input
			bind:this={input}
			bind:value={text}
			maxlength={MAX_TAG_LENGTH}
			aria-label="Add tag"
			placeholder="Add tag"
			autocomplete="off"
			enterkeyhint="done"
		/>
		<button
			type="submit"
			aria-label="Add new tag"
			disabled={!canEdit}
			onpointerdown={keepFocus}
			onmousedown={keepFocus}
		>
			<Icon name="add" />
		</button>
	</form>

	{#if tags.length > 0}
		<ul class="tag-list" aria-label="Tags">
			{#each tags as tag (tag)}
				<li>
					<div class="tag-row">
						<button
							class="swatch"
							type="button"
							style:--tag={tagColor(settings, tag)}
							aria-label="Color of {tag}"
							aria-expanded={coloring === tag}
							onclick={() => (coloring = coloring === tag ? null : tag)}
						></button>
						<span class="name">{tag}</span>
						<button
							class="remove"
							type="button"
							aria-label="Delete tag {tag}"
							disabled={!canEdit}
							onclick={() => onDelete(tag)}
						>
							<Icon name="delete" />
						</button>
					</div>
					{#if coloring === tag}
						<div class="colors" role="group" aria-label="Colors of {tag}">
							{#each colorIndexes as index (index)}
								<button
									class="dot"
									type="button"
									style:--tag={colorVar(index)}
									aria-label="Color {index + 1}"
									aria-pressed={tagColorIndex(settings, tag) === index}
									disabled={!canEdit}
									onclick={() => chooseColor(tag, index)}
								></button>
							{/each}
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	<div class="actions">
		<button type="button" onclick={onClose}>Close</button>
	</div>
</Dialog>

{#if confirming}
	<ConfirmDialog
		question={severalTagsQuestion(several)}
		detail="The tags stay on the list. Only the first tag on each item is kept."
		confirmLabel="Keep first tags"
		onConfirm={confirmSingle}
		onClose={() => (confirming = false)}
	/>
{/if}

<style>
	.segmented {
		display: flex;
		margin-bottom: 0.5rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		overflow: hidden;
	}

	.segmented button {
		flex: 1;
		min-width: 0;
		padding: 0 0.5rem;
		border: 0;
		border-radius: 0;
		background: transparent;
		color: var(--text);
		font-weight: 600;
	}

	.segmented button.on {
		background: var(--primary);
		color: var(--primary-text);
	}

	.switch {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		min-height: var(--touch);
		font-weight: 500;
		cursor: pointer;
	}

	/* Indented under "Show tags on items"; greyed out when that is off. */
	.switch.sub {
		padding-left: 1rem;
		font-weight: 400;
	}

	.switch.sub.disabled {
		color: var(--text-muted);
		cursor: default;
	}

	form.add {
		display: flex;
		gap: 0.5rem;
		margin: 0.5rem 0;
	}

	form.add input {
		flex: 1;
		min-width: 0;
	}

	form.add button {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--primary);
	}

	.tag-list {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.tag-row {
		display: flex;
		align-items: center;
		min-height: var(--touch);
		border-top: 1px solid var(--border);
	}

	/* A 44px tap area with a colored disc inside. */
	.swatch {
		width: var(--touch);
		height: var(--touch);
		min-width: 0;
		min-height: 0;
		padding: 0;
		display: grid;
		place-items: center;
		border: 0;
		background: transparent;
	}

	.swatch::before {
		content: '';
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 50%;
		background: var(--tag);
	}

	.name {
		flex: 1;
		min-width: 0;
		overflow-wrap: anywhere;
		font-weight: 600;
	}

	.remove {
		min-width: var(--touch);
		min-height: var(--touch);
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--danger);
	}

	/* The seven colors in a row; each one a 44px tap area. */
	.colors {
		display: flex;
		flex-wrap: wrap;
		gap: 0;
		padding-bottom: 0.25rem;
	}

	.dot {
		width: var(--touch);
		height: var(--touch);
		min-width: 0;
		min-height: 0;
		padding: 0;
		display: grid;
		place-items: center;
		border: 0;
		background: transparent;
	}

	.dot::before {
		content: '';
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		background: var(--tag);
	}

	.dot[aria-pressed='true']::before {
		box-shadow:
			0 0 0 3px var(--surface),
			0 0 0 5px var(--text);
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		margin-top: 0.75rem;
	}
</style>
