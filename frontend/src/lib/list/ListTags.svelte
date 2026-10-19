<!--
	The list's tags. A tap on a tag chip adds it to the filter, and a tap again
	removes it; the items must have every chosen tag. In Options mode there is
	an "Add Tag" field, and each chip gets a × to delete the tag from the list.
-->
<script lang="ts">
	import { MAX_TAG_LENGTH } from '#lib/ui/field-limits.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import { keepFocus } from '#lib/ui/focus.ts';
	import { newTag, tagColor } from './tags';

	let {
		tags,
		filter,
		editing,
		canEdit,
		onToggleFilter,
		onClear,
		onAdd,
		onDelete
	}: {
		/** The list's tags, sorted ignoring case. */
		tags: readonly string[];
		/** Whether shared-data tag mutations are authorized. */
		canEdit: boolean;
		/** The tags the items are filtered by: an item must have all of them. */
		filter: readonly string[];
		/** Options mode: adding and deleting tags. */
		editing: boolean;
		/** Adds the tag to the filter, or removes it when it is in the filter. */
		onToggleFilter: (tag: string) => void;
		/** Removes every tag from the filter. Shown as "Clear" while a filter is on. */
		onClear: () => void;
		/** Adds a tag; true when the field should be cleared. */
		onAdd: (tag: string) => Promise<boolean>;
		onDelete: (tag: string) => void;
	} = $props();

	let text = $state('');
	let input = $state<HTMLInputElement>();

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

{#if editing}
	<form onsubmit={submit} novalidate>
		<input
			bind:this={input}
			bind:value={text}
			maxlength={MAX_TAG_LENGTH}
			aria-label="Add Tag"
			placeholder="Add Tag"
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
{/if}

{#if tags.length > 0}
	<ul class="chips" aria-label="Tags">
		{#each tags as tag (tag)}
			<li style:--tag={tagColor(tag)}>
				<button
					class="chip"
					class:on={filter.includes(tag)}
					type="button"
					aria-pressed={filter.includes(tag)}
					onclick={() => onToggleFilter(tag)}
				>
					{tag}
				</button>
				{#if editing}
					<button
						class="remove"
						type="button"
						aria-label="Delete tag {tag}"
						disabled={!canEdit}
						onclick={() => onDelete(tag)}
					>
						<Icon name="close" />
					</button>
				{/if}
			</li>
		{/each}
		{#if filter.length > 0}
			<li>
				<button class="chip clear" type="button" onclick={onClear}>Clear</button>
			</li>
		{/if}
	</ul>
{/if}

<style>
	form {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	input {
		flex: 1;
		min-width: 0;
	}

	form button {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--primary);
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		list-style: none;
		margin: 0 0 0.5rem;
		padding: 0;
	}

	li {
		display: flex;
		align-items: center;
	}

	/* Outlined in the tag's color; filled while it filters the items. The
	   tap area is 44px tall: the extra 4px above and below reach into the
	   8px gap between rows of chips, so they never overlap. */
	.chip {
		position: relative;
		min-height: 2.25rem;
		padding: 0 0.75rem;
		border: 1.5px solid var(--tag);
		border-radius: 999px;
		color: var(--tag);
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	/* Inset counts from the inside of the 1.5px border, so -5.5px reaches 4px
	   past the chip's edge on each side. */
	.chip::before {
		content: '';
		position: absolute;
		inset: -5.5px 0;
	}

	.chip.on {
		background: var(--tag);
		color: var(--tag-text);
	}

	/* Not a tag: grey, so it does not look like one. */
	.chip.clear {
		--tag: var(--text-muted);
	}

	.remove {
		min-width: var(--touch);
		min-height: var(--touch);
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--tag);
	}
</style>
