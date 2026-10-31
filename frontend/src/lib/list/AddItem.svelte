<!--
	The "Add or Search" field. Enter (or the Add button) adds the typed text,
	unless an arrow key highlights a suggestion; Enter then adds or restores the
	highlighted name. Clicking or tapping a suggestion also selects it. Escape
	closes the list. Leaving the field hides the list (the text stays); coming
	back shows it again. The field keeps focus after selecting a suggestion, so
	the next item can be typed at once.
-->
<script lang="ts">
	import { MAX_NAME_LENGTH } from '#lib/ui/field-limits.ts';
	import type { Item } from '#lib/data/index.ts';
	import { itemSuggestions, normalizeItemName, usualItemSuggestions } from './items';
	import { keepFocus } from '#lib/ui/focus.ts';

	let {
		items,
		canEdit,
		text = $bindable(''),
		onAdd
	}: {
		/** All items of the list, hidden ones included. */
		items: readonly Item[];
		/** Whether edits may start (offline they are queued). */
		canEdit: boolean;
		/** The field text also drives local search. */
		text?: string;
		/** Adds the (normalized) name; true when the field should be cleared. */
		onAdd: (name: string) => Promise<boolean>;
	} = $props();
	let input = $state<HTMLInputElement>();
	const suggestions = $derived(itemSuggestions(items, text));
	const usual = $derived(usualItemSuggestions(items, text));
	/** The highlighted suggestion, tracked by name so live sorting cannot change it. */
	let activeName = $state<string | null>(null);
	/** Escape hides the suggestions until the text changes. */
	let closed = $state(false);
	/** Suggestions show only while the field has focus. */
	let focused = $state(false);
	const shown = $derived(closed || !focused ? [] : suggestions);
	const active = $derived(activeName === null ? -1 : shown.indexOf(activeName));
	// Unique ids on the page, for the ARIA links between field and suggestions.
	const listId = $props.id();

	// A live update can remove the highlighted suggestion; do not revive it later.
	$effect(() => {
		if (activeName !== null && !shown.includes(activeName)) activeName = null;
	});

	function blurred() {
		focused = false;
		activeName = null;
	}

	function typed() {
		activeName = null;
		closed = false;
	}

	// Arrow keys move the highlight and wrap around at either end.
	function keydown(event: KeyboardEvent) {
		const count = shown.length;
		if (event.key === 'ArrowDown' && count > 0) {
			event.preventDefault();
			activeName = shown[(active + 1) % count];
		} else if (event.key === 'ArrowUp' && count > 0) {
			event.preventDefault();
			activeName = shown[active <= 0 ? count - 1 : active - 1];
		} else if (event.key === 'Escape' && count > 0) {
			event.preventDefault();
			closed = true;
			activeName = null;
		}
	}

	async function add(raw: string) {
		const name = normalizeItemName(raw);
		if (!name) return;
		if (!canEdit) {
			text = name;
			return;
		}
		const sent = text;
		activeName = null;
		input?.focus();
		const clear = await onAdd(name);
		// Clear only if nothing new was typed while waiting for the server.
		if (clear && text === sent) text = '';
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		void add(active >= 0 && shown[active] ? shown[active] : text);
	}
</script>

<div class="add">
	<form onsubmit={submit} novalidate>
		<input
			bind:this={input}
			bind:value={text}
			maxlength={MAX_NAME_LENGTH}
			oninput={typed}
			onkeydown={keydown}
			onfocus={() => (focused = true)}
			onblur={blurred}
			role="combobox"
			aria-autocomplete="list"
			aria-expanded={shown.length > 0}
			aria-controls={shown.length > 0 ? listId : undefined}
			aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
			aria-label="Add or Search"
			placeholder="Add or Search"
			autocomplete="off"
			autocapitalize="none"
			enterkeyhint="enter"
		/>
		<button
			class="primary"
			type="submit"
			disabled={!canEdit}
			onpointerdown={keepFocus}
			onmousedown={keepFocus}
		>
			Add
		</button>
	</form>

	{#if usual.length > 0}
		<div class="usual">
			<p id="{listId}-usual-label" class="usual-label">Usual items</p>
			<ul class="usual-items" aria-labelledby="{listId}-usual-label">
				{#each usual as name (name)}
					<li>
						<button type="button" disabled={!canEdit} onclick={() => add(name)}>
							{name}
						</button>
					</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if shown.length > 0}
		<!-- A combobox's popup: screen readers announce the highlighted option
		     while the focus stays in the field. -->
		<ul id={listId} role="listbox" aria-label="Suggestions">
			{#each shown as name, index (name)}
				<!-- Keyboard handling stays on the combobox; options are not tab stops. -->
				<!-- Prevent touch mousedown from unmounting an option before its click. -->
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<li
					id="{listId}-{index}"
					class:active={index === active}
					role="option"
					aria-selected={index === active}
					onmousedown={keepFocus}
					onclick={() => add(name)}
				>
					{name}
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

	li {
		display: flex;
		align-items: center;
		width: 100%;
		min-height: var(--touch);
		padding: 0 1rem;
		text-align: left;
		overflow-wrap: anywhere;
		cursor: pointer;
	}

	li.active {
		background: var(--border);
	}

	.usual {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.25rem 0.5rem;
		padding-bottom: 0.5rem;
	}

	.usual-label {
		margin: 0;
		color: var(--text-muted);
	}

	ul.usual-items {
		position: static;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin: 0;
		padding: 0;
		background: transparent;
		border-radius: 0;
		box-shadow: none;
	}

	ul.usual-items li {
		width: auto;
		min-height: 0;
		padding: 0;
	}

	.usual-items button {
		width: auto;
		min-height: var(--touch);
		padding: 0 0.75rem;
		border-color: var(--border);
		background: var(--surface);
		text-align: left;
		overflow-wrap: anywhere;
	}
</style>
