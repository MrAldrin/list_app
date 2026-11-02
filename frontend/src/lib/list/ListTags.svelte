<!--
	The list's tags as filter chips, in one line that scrolls sideways. A tap on
	a chip adds it to the filter, and a tap again removes it; the items must have
	every chosen tag. While Options is open a tap on a chip opens its "Edit Tag"
	card instead, and each chip shows a pencil. A right click always opens the
	card. A mouse can drag the row, and its wheel scrolls it sideways. New tags
	are added in Options > Tags.
-->
<script lang="ts">
	import type { TagSettings } from '#lib/data/index.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import TagDialog from './TagDialog.svelte';
	import { tagColor, tagColorIndex } from './tags';

	let {
		tags,
		filter,
		tagSettings,
		optionsOpen,
		canEdit,
		onToggleFilter,
		onClear,
		onRename,
		onDelete,
		onColor
	}: {
		/** The list's tags, sorted ignoring case. */
		tags: readonly string[];
		/** The tags the items are filtered by. */
		filter: readonly string[];
		tagSettings: TagSettings;
		/** Options is open: a tap on a chip opens its card instead of filtering. */
		optionsOpen: boolean;
		/** Whether shared-data tag mutations are authorized. */
		canEdit: boolean;
		/** Adds the tag to the filter, or removes it when it is in the filter. */
		onToggleFilter: (tag: string) => void;
		/** Removes every tag from the filter. Shown as "Clear" while a filter is on. */
		onClear: () => void;
		/** Renames a tag to the new name; true when the card should close. */
		onRename: (tag: string, name: string) => Promise<boolean>;
		/** Deletes the tag (the parent offers "Undo"). */
		onDelete: (tag: string) => void;
		onColor: (tag: string, index: number) => void;
	} = $props();

	/** A mouse press that moves this far is a drag of the row, not a tap. */
	const DRAG_PX = 5;

	/** The tag whose card is open, or null. */
	let openTagName = $state<string | null>(null);

	let row = $state<HTMLUListElement>();
	let fadeStart = $state(false);
	let fadeEnd = $state(false);
	let dragging = $state(false);
	/** The mouse press in progress: where it began and where the pointer was last. */
	let drag: { startX: number; lastX: number; moved: boolean } | null = null;
	/** A drag just ended: the click its release makes does nothing. */
	let dragClick = false;

	function chipClick(tag: string) {
		if (optionsOpen) openTagName = tag;
		else onToggleFilter(tag);
	}

	/** A right click opens the card at any time; the browser menu does not show. */
	function rightClick(event: MouseEvent, tag: string) {
		event.preventDefault();
		openTagName = tag;
	}

	function dragStart(event: PointerEvent) {
		if (event.pointerType !== 'mouse' || event.button !== 0) return;
		drag = { startX: event.clientX, lastX: event.clientX, moved: false };
		dragClick = false;
	}

	function dragMove(event: PointerEvent) {
		if (!drag || !row) return;
		const dx = event.clientX - drag.lastX;
		drag.lastX = event.clientX;
		if (!drag.moved) {
			if (Math.abs(event.clientX - drag.startX) <= DRAG_PX) return;
			drag.moved = true;
			dragging = true;
			// Keep following the pointer when it leaves the row.
			row.setPointerCapture(event.pointerId);
		}
		row.scrollLeft -= dx;
	}

	function dragEnd() {
		if (!drag) return;
		if (drag.moved) {
			dragClick = true;
			dragging = false;
		}
		drag = null;
	}

	/** The click that ends a drag is not a tap: it must not filter or open a card. */
	function swallowDragClick(event: MouseEvent) {
		if (!dragClick) return;
		dragClick = false;
		event.preventDefault();
		event.stopPropagation();
	}

	/** Updates the edge fades: each shows on the side that still has chips hidden. */
	function updateFades() {
		if (!row) return;
		const max = row.scrollWidth - row.clientWidth;
		fadeStart = row.scrollLeft > 1;
		fadeEnd = row.scrollLeft < max - 1;
	}

	$effect(() => {
		// Runs again when the chips change; the DOM is updated by then.
		void tags;
		void filter;
		void row;
		updateFades();
	});

	// A listener, not `onwheel`: only a listener that is not passive may cancel the scroll.
	$effect(() => {
		const element = row;
		if (!element) return;
		const wheel = (event: WheelEvent) => {
			// Only a vertical turn of the wheel moves the row, and only while it can move that way.
			if (event.deltaY === 0 || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
			const amount =
				event.deltaMode === WheelEvent.DOM_DELTA_LINE ? event.deltaY * 16 : event.deltaY;
			const max = element.scrollWidth - element.clientWidth;
			const next = Math.min(max, Math.max(0, element.scrollLeft + amount));
			if (next === element.scrollLeft) return;
			event.preventDefault();
			element.scrollLeft = next;
		};
		element.addEventListener('wheel', wheel, { passive: false });
		return () => element.removeEventListener('wheel', wheel);
	});

	function deleteOpenTag(tag: string) {
		openTagName = null;
		onDelete(tag);
	}
</script>

<svelte:window onresize={updateFades} />

{#if tags.length > 0}
	<ul
		class="chips"
		class:dragging
		class:fade-start={fadeStart}
		class:fade-end={fadeEnd}
		aria-label="Tags"
		bind:this={row}
		onscroll={updateFades}
		onpointerdown={dragStart}
		onpointermove={dragMove}
		onpointerup={dragEnd}
		onpointercancel={dragEnd}
		onclickcapture={swallowDragClick}
	>
		{#each tags as tag (tag)}
			{@const on = filter.includes(tag)}
			<li style:--tag={tagColor(tagSettings, tag)}>
				<button
					class="chip"
					class:on
					type="button"
					aria-pressed={on}
					oncontextmenu={(event) => rightClick(event, tag)}
					onclick={() => chipClick(tag)}
				>
					{tag}
					{#if optionsOpen}
						<span class="edit-mark"><Icon name="edit" /></span>
					{/if}
				</button>
			</li>
		{/each}
		{#if filter.length > 0}
			<li>
				<button class="chip clear" type="button" onclick={onClear}>Clear</button>
			</li>
		{/if}
	</ul>
{/if}

{#if openTagName !== null && tags.includes(openTagName)}
	{@const tag = openTagName}
	<TagDialog
		{tag}
		colorIndex={tagColorIndex(tagSettings, tag)}
		{canEdit}
		onColor={(index) => onColor(tag, index)}
		onRename={(name) => onRename(tag, name)}
		onDelete={() => deleteOpenTag(tag)}
		onClose={() => (openTagName = null)}
	/>
{/if}

<style>
	/* One line that scrolls sideways; the scrollbar is hidden, the swipe still works. */
	/* The vertical padding keeps the chips' 4px tap extension from being clipped. */
	/* No scroll-snap: it breaks mouse drag in Firefox. */
	.chips {
		display: flex;
		flex-wrap: nowrap;
		gap: 0.5rem;
		overflow-x: auto;
		overflow-y: hidden;
		-webkit-overflow-scrolling: touch;
		scrollbar-width: none;
		list-style: none;
		margin: -0.25rem 0 0.25rem;
		padding: 0.25rem 0;
		cursor: grab;
		user-select: none;
		-webkit-user-select: none;
	}

	.chips.dragging,
	.chips.dragging .chip {
		cursor: grabbing;
	}

	/* Soft edges where chips are hidden: a fade on the side that can still scroll. */
	.chips.fade-start {
		mask-image: linear-gradient(to right, transparent, #000 2rem);
		-webkit-mask-image: linear-gradient(to right, transparent, #000 2rem);
	}

	.chips.fade-end {
		mask-image: linear-gradient(to right, #000 calc(100% - 2rem), transparent);
		-webkit-mask-image: linear-gradient(to right, #000 calc(100% - 2rem), transparent);
	}

	.chips.fade-start.fade-end {
		mask-image: linear-gradient(
			to right,
			transparent,
			#000 2rem,
			#000 calc(100% - 2rem),
			transparent
		);
		-webkit-mask-image: linear-gradient(
			to right,
			transparent,
			#000 2rem,
			#000 calc(100% - 2rem),
			transparent
		);
	}

	.chips::-webkit-scrollbar {
		display: none;
	}

	li {
		display: flex;
		flex-shrink: 0;
		align-items: center;
	}

	/* Outlined in the tag's color; filled while it filters the items. The
	   tap area is 44px tall: the extra 4px above and below reach into the
	   padding of the row, so they never overlap. */
	.chip {
		position: relative;
		min-height: 2.25rem;
		padding: 0 0.75rem;
		border: 1.5px solid var(--tag);
		border-radius: 999px;
		color: var(--tag);
		font-weight: 600;
		white-space: nowrap;
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		cursor: inherit;
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

	/* The pencil shown while Options is open; it takes the chip's text color. */
	.edit-mark {
		display: grid;
		width: 1rem;
		height: 1rem;
	}

	.edit-mark :global(svg) {
		width: 1rem;
		height: 1rem;
	}
</style>
