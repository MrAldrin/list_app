<!--
	The list's tags. A tap on a tag chip shows only the items with that tag
	(tap again to show all). In Options mode there is an "Add Tag" field, and
	each chip gets a × to delete the tag from the list.
-->
<script lang="ts">
	import Icon from '#lib/ui/Icon.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import { newTag, tagColor } from './tags';

	let {
		tags,
		filter,
		editing,
		canWrite,
		onFilter,
		onAdd,
		onDelete
	}: {
		/** The list's tags, sorted ignoring case. */
		tags: readonly string[];
		/** Whether shared-data tag mutations are authorized. */
		canWrite: boolean;
		/** The tag the items are filtered by, or null. */
		filter: string | null;
		/** Options mode: adding and deleting tags. */
		editing: boolean;
		onFilter: (tag: string | null) => void;
		/** Adds a tag; true when the field should be cleared. */
		onAdd: (tag: string) => Promise<boolean>;
		onDelete: (tag: string) => void;
	} = $props();

	let text = $state('');
	let input = $state<HTMLInputElement>();

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (!canWrite) return;
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

	function keepFocus(event: Event) {
		event.preventDefault();
	}
</script>

{#if editing}
	<form onsubmit={submit} novalidate>
		<input
			bind:this={input}
			bind:value={text}
			aria-label="Add Tag"
			placeholder="Add Tag"
			autocomplete="off"
			enterkeyhint="done"
		/>
		<button
			type="submit"
			aria-label="Add new tag"
			disabled={!canWrite}
			onpointerdown={keepFocus}
			onmousedown={keepFocus}
		>
			<Icon name="add" />
		</button>
	</form>
{/if}

{#if tags.length > 0}
	<ul class="chips" aria-label="Tags">
		{#each tags as tag, index (tag)}
			<li style:--tag={tagColor(index)}>
				<button
					class="chip"
					class:on={filter === tag}
					type="button"
					aria-pressed={filter === tag}
					onclick={() => onFilter(filter === tag ? null : tag)}
				>
					{tag}
				</button>
				{#if editing}
					<button
						class="remove"
						type="button"
						aria-label="Delete tag {tag}"
						disabled={!canWrite}
						onclick={() => onDelete(tag)}
					>
						<Icon name="close" />
					</button>
				{/if}
			</li>
		{/each}
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

	/* Outlined in the tag's color; filled while it filters the items. */
	.chip {
		min-height: 2.25rem;
		padding: 0 0.75rem;
		border: 1.5px solid var(--tag);
		border-radius: 999px;
		color: var(--tag);
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	.chip.on {
		background: var(--tag);
		color: var(--tag-text);
	}

	.remove {
		min-width: 2.25rem;
		min-height: 2.25rem;
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--tag);
	}
</style>
