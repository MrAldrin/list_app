<!--
	The "Add or Search" field. Enter (or the Add button) adds the item, or
	brings back a checked one. While typing, it suggests up to three names
	already in the list. The field keeps focus, so the next item can be typed
	at once.
-->
<script lang="ts">
	import type { Item } from '#lib/data/index.ts';
	import { itemSuggestions, normalizeItemName } from './items';

	let {
		items,
		onAdd
	}: {
		/** All items of the list, hidden ones included. */
		items: readonly Item[];
		/** Adds the (normalized) name; true when the field should be cleared. */
		onAdd: (name: string) => Promise<boolean>;
	} = $props();

	let text = $state('');
	let input = $state<HTMLInputElement>();
	const suggestions = $derived(itemSuggestions(items, text));

	async function add(raw: string) {
		const name = normalizeItemName(raw);
		if (!name) return;
		const sent = text;
		input?.focus();
		const clear = await onAdd(name);
		// Clear only if nothing new was typed while waiting for the server.
		if (clear && text === sent) text = '';
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		void add(text);
	}

	// Pressing a button would move the focus away from the field (and close
	// the phone keyboard). Stopping the press's default keeps it in the field.
	function keepFocus(event: Event) {
		event.preventDefault();
	}
</script>

<div class="add">
	<form onsubmit={submit} novalidate>
		<input
			bind:this={input}
			bind:value={text}
			aria-label="Add or Search"
			placeholder="Add or Search"
			autocomplete="off"
			autocapitalize="none"
			enterkeyhint="enter"
		/>
		<button class="primary" type="submit" onpointerdown={keepFocus} onmousedown={keepFocus}>
			Add
		</button>
	</form>

	{#if suggestions.length > 0}
		<ul aria-label="Suggestions">
			{#each suggestions as name (name)}
				<li>
					<button
						type="button"
						onpointerdown={keepFocus}
						onmousedown={keepFocus}
						onclick={() => add(name)}
					>
						{name}
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	/* The suggestions float over the items below, so the list does not jump
	   while typing. */
	.add {
		position: relative;
	}

	form {
		display: flex;
		gap: 0.5rem;
		margin: 0.5rem 0;
	}

	input {
		flex: 1;
		min-width: 0;
	}

	ul {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		z-index: 5;
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0.25rem 0;
		background: var(--surface);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
	}

	li button {
		width: 100%;
		text-align: left;
		border-radius: 0;
		overflow-wrap: anywhere;
	}
</style>
