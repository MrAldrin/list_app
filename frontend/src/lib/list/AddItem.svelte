<!--
	The "Add or Search" field. Enter (or the Add button) adds the item, or
	brings back a checked one. While typing, it suggests up to three names
	already in the list; arrow keys highlight one and Enter picks it, Escape
	closes the list. The field keeps focus, so the next item can be typed at
	once.
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
	/** The suggestion highlighted with the arrow keys; -1 for none. */
	let active = $state(-1);
	/** Escape hides the suggestions until the text changes. */
	let closed = $state(false);
	const shown = $derived(closed ? [] : suggestions);

	function typed() {
		active = -1;
		closed = false;
	}

	// Arrow keys move the highlight and wrap around at either end.
	function keydown(event: KeyboardEvent) {
		const count = shown.length;
		if (event.key === 'ArrowDown' && count > 0) {
			event.preventDefault();
			active = (active + 1) % count;
		} else if (event.key === 'ArrowUp' && count > 0) {
			event.preventDefault();
			active = active <= 0 ? count - 1 : active - 1;
		} else if (event.key === 'Escape' && count > 0) {
			event.preventDefault();
			closed = true;
			active = -1;
		}
	}

	async function add(raw: string) {
		const name = normalizeItemName(raw);
		if (!name) return;
		const sent = text;
		active = -1;
		input?.focus();
		const clear = await onAdd(name);
		// Clear only if nothing new was typed while waiting for the server.
		if (clear && text === sent) text = '';
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		void add(active >= 0 && shown[active] ? shown[active] : text);
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
			oninput={typed}
			onkeydown={keydown}
			aria-activedescendant={active >= 0 ? `suggestion-${active}` : undefined}
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

	{#if shown.length > 0}
		<ul aria-label="Suggestions">
			{#each shown as name, index (name)}
				<li>
					<button
						id="suggestion-{index}"
						class:active={index === active}
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
	/* The field sticks just below the list page's top bar while the page
	   scrolls. Sticky also anchors the suggestions, which float over the
	   items below, so the list does not jump while typing. */
	.add {
		position: sticky;
		top: var(--touch);
		z-index: 10;
		background: var(--bg);
	}

	form {
		display: flex;
		gap: 0.5rem;
		padding: 0.5rem 0;
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

	li button.active {
		background: var(--border);
	}
</style>
