<!--
	The room name in the room header (the page's h1). Tapping the name opens a
	small panel under the title: the remembered rooms (the current one has a
	check mark and closes the panel), "+ Add room", and a small "admin" link at
	the foot. The panel is a popover next to the heading, not inside it, so the
	heading's name stays the room name.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { RoomHandle } from '#lib/data/index.ts';
	import { readRememberedRooms, type RememberedRoom } from './remembered-rooms.ts';

	let { room }: { room: RoomHandle } = $props();

	const menuId = $props.id();
	let button = $state<HTMLButtonElement>();
	let menu = $state<HTMLDivElement>();
	let open = $state(false);
	/** Read as the panel opens: other rooms may have changed. */
	let rooms = $state<RememberedRoom[]>([]);
	const name = $derived(room.store.room?.name ?? '');

	// A popover sits in the browser's top layer, outside the page layout, so
	// it is placed by hand: under the title, left edge lined up with the name.
	function opened(event: ToggleEvent) {
		open = event.newState === 'open';
		if (!open || !button || !menu) return;
		// The current room always comes first, even if the cookie list lacks it.
		rooms = [
			{ slug: room.slug, name },
			...readRememberedRooms().filter((item) => item.slug !== room.slug)
		];
		const box = button.getBoundingClientRect();
		menu.style.top = `${box.bottom + 4}px`;
		const left = Math.min(box.left, window.innerWidth - menu.offsetWidth - 8);
		menu.style.left = `${Math.max(8, left)}px`;
	}

	function close() {
		menu?.hidePopover();
	}

	/** Opens another remembered room. It asks for its password if access is gone. */
	function switchRoom(slug: string) {
		close();
		void goto(resolve('/room/[slug]', { slug }));
	}

	/** Opens the start page to enter another room. `?add` skips the jump to the last room. */
	function addRoom() {
		close();
		void goto(`${resolve('/')}?add`);
	}

	function openAdmin() {
		close();
		void goto(resolve('/admin'));
	}
</script>

<h1>
	<button
		bind:this={button}
		class="switch"
		type="button"
		aria-label="Switch room, current: {name}"
		aria-expanded={open}
		popovertarget={menuId}
	>
		<span class="name">{name}</span>
		<svg
			viewBox="0 0 24 24"
			width="20"
			height="20"
			aria-hidden="true"
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			stroke-linecap="round"
			stroke-linejoin="round"
		>
			<path d="m6 9 6 6 6-6" />
		</svg>
	</button>
</h1>

<div bind:this={menu} id={menuId} class="menu" popover="auto" ontoggle={opened}>
	<div role="group" aria-label="Rooms">
		<p class="heading">Rooms</p>
		{#each rooms as item (item.slug)}
			{#if item.slug === room.slug}
				<button type="button" class="item" aria-current="true" onclick={close}>
					<span class="mark" aria-hidden="true">✓</span>
					<span class="room-name">{item.name}</span>
				</button>
			{:else}
				<button type="button" class="item" onclick={() => switchRoom(item.slug)}>
					<span class="mark" aria-hidden="true"></span>
					<span class="room-name">{item.name}</span>
				</button>
			{/if}
		{/each}
		<hr />
		<button type="button" class="item" onclick={addRoom}>+ Add room</button>
	</div>
	<hr />
	<div class="foot">
		<button type="button" class="admin" onclick={openAdmin}>admin</button>
	</div>
</div>

<style>
	h1 {
		flex: 1;
		min-width: 0;
		font-size: 1.5rem;
	}

	/* The name and chevron button. It shrinks and ends the name with "…". */
	.switch {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		max-width: 100%;
		min-width: 0;
		min-height: var(--touch);
		padding: 0 0.25rem;
		font: inherit;
		color: var(--text);
	}

	.name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.switch svg {
		flex-shrink: 0;
	}

	.switch[aria-expanded='true'] svg {
		transform: rotate(180deg);
	}

	.menu {
		/* Undo the browser's centered popover; `opened` sets top and left. */
		position: fixed;
		inset: auto;
		margin: 0;
		width: min(18rem, calc(100vw - 16px));
		padding: 0.25rem 0;
		border: none;
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow);
	}

	.heading {
		margin: 0;
		padding: 0.25rem 1rem 0;
		color: var(--text-muted);
		font-size: 0.85em;
	}

	.item {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		min-height: var(--touch);
		padding: 0 1rem;
		border: none;
		border-radius: 0;
		background: none;
		text-align: left;
	}

	.mark {
		flex-shrink: 0;
		width: 1em;
		text-align: center;
	}

	/* A long room name ends with "…" instead of widening the panel. */
	.room-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.item[aria-current='true'] {
		font-weight: 700;
	}

	.foot {
		display: flex;
		justify-content: flex-end;
	}

	/* A small text link look, with the same 44px tap area as other buttons. */
	.admin {
		min-height: var(--touch);
		padding: 0 1rem;
		border: none;
		background: none;
		color: var(--text-muted);
		font-size: 0.9rem;
		text-decoration: underline;
	}

	hr {
		margin: 0.25rem 0;
		border: none;
		border-top: 1px solid var(--border);
	}
</style>
