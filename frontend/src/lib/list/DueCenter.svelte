<!--
	The due bell: a button with the count of unchecked items overdue or due
	today or tomorrow, and a panel listing every dated, unchecked item in
	groups (Overdue, Today, Tomorrow, Next 7 days, Later). The panel shows the
	room, or only the list on screen when `listUid` is set. A tap on an item
	opens its list with the item revealed. Opening the panel never clears the count. Live updates change the panel's content
	but never move focus.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import type { RoomHandle } from '#lib/data/index.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import PolicyEditor from '#lib/reminders/PolicyEditor.svelte';
	import type { PolicyScope } from '#lib/reminders/api.ts';
	import Icon from '#lib/ui/Icon.svelte';
	import { deviceZone } from '#lib/reminders/device-zone.svelte.ts';
	import { formatItemDate } from './items.ts';
	import { dueClock } from './due-clock.svelte.ts';
	import {
		badgeText,
		DUE_GROUP_TITLES,
		dueRows,
		dueSections,
		dueTag,
		dueTally,
		type DueRow
	} from './due-reminders.ts';
	import { revealHref } from './reveal.ts';

	let {
		room,
		listUid,
		roomScope = false
	}: {
		room: RoomHandle;
		/** The list on screen; unset on the room page. */
		listUid?: string;
		/** Whether the room scope may be shown (room pages, not share links). */
		roomScope?: boolean;
	} = $props();

	let open = $state(false);
	let policyTarget = $state<{ scope: PolicyScope; uid?: string } | null>(null);
	const headingBase = $props.id();

	const now = $derived(dueClock.now);
	const scopedItems = $derived(
		listUid
			? room.store.itemsOf(listUid)
			: room.store.lists.flatMap((list) => room.store.itemsOf(list.uid))
	);
	const tally = $derived(dueTally(scopedItems, now, roomScope ? deviceZone(room) : undefined));
	const rows = $derived(
		dueRows(
			scopedItems,
			(uid) => room.store.list(uid)?.name ?? '',
			now,
			roomScope ? deviceZone(room) : undefined
		)
	);
	const sections = $derived(dueSections(rows));
	const badge = $derived(badgeText(tally.count));
	const bellLabel = $derived(
		tally.count === 0
			? 'Due items: none due'
			: `Due items: ${tally.count} due, ${tally.overdue} overdue`
	);

	/** The link for a row: the list page with the item revealed; this page's own list when it is the one on screen. */
	function hrefOf(row: DueRow): string {
		if (listUid && row.item.list_uid === listUid)
			return revealHref(page.url.pathname, row.item.uid);
		const slug = room.store.list(row.item.list_uid)?.slug ?? '';
		return revealHref(
			resolve('/room/[slug]/list/[list]', { slug: room.slug, list: slug }),
			row.item.uid
		);
	}
</script>

<button
	class="bell"
	type="button"
	aria-label={bellLabel}
	aria-haspopup="dialog"
	onclick={() => (open = true)}
>
	<Icon name="notifications" />
	{#if tally.count > 0}
		<span class="badge" class:overdue={tally.overdue > 0} aria-hidden="true">{badge}</span>
	{/if}
</button>

{#if policyTarget}
	<PolicyEditor
		{room}
		scope={policyTarget.scope}
		uid={policyTarget.uid}
		onClose={() => {
			policyTarget = null;
			open = true;
		}}
	/>
{:else if open}
	<Dialog title="Due items" onClose={() => (open = false)}>
		{#if roomScope}
			<button
				type="button"
				onclick={() => {
					open = false;
					policyTarget = { scope: 'room' };
				}}>Room reminder policy</button
			>
			{#if listUid}<button
					type="button"
					onclick={() => {
						open = false;
						policyTarget = { scope: 'list', uid: listUid };
					}}>List reminder policy</button
				>{/if}
		{/if}
		{#if room.store.unconfirmedView}
			<p class="saved" role="note">Saved data. It may not be up to date.</p>
		{/if}
		{#if sections.length === 0}
			<p class="empty">No dated items. Add a date to an item to see it here.</p>
		{:else}
			{#each sections as section (section.group)}
				<section class="group" aria-labelledby="{headingBase}-{section.group}">
					<h3 id="{headingBase}-{section.group}">
						{DUE_GROUP_TITLES[section.group]} <span class="count">({section.rows.length})</span>
					</h3>
					<ul>
						{#each section.rows as row (row.item.uid)}
							{@const tag = dueTag(row.group)}
							<li class="due-entry">
								<a class="due-row" href={hrefOf(row)} onclick={() => (open = false)}>
									<span class="name">{row.item.name}</span>
									{#if !listUid}
										<span class="where">{row.listName}</span>
									{/if}
									<span class="when">{formatItemDate(row.date)}</span>
									{#if tag}
										<span class="tag {tag.tone}">{tag.text}</span>
									{/if}
								</a>
								{#if roomScope}<button
										class="item-policy"
										type="button"
										aria-label={`Private reminder settings for ${row.item.name}`}
										onclick={() => {
											open = false;
											policyTarget = { scope: 'item', uid: row.item.uid };
										}}><Icon name="notifications" /><span>Reminder settings</span></button
									>{/if}
							</li>
						{/each}
					</ul>
				</section>
			{/each}
		{/if}
	</Dialog>
{/if}

<style>
	.bell {
		position: relative;
		min-width: var(--touch);
		min-height: var(--touch);
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--text);
	}

	/* The count sits on the bell; red when something is overdue. */
	.badge {
		position: absolute;
		top: 2px;
		right: 0;
		min-width: 1.25rem;
		padding: 0 0.3rem;
		border-radius: 0.625rem;
		background: var(--primary);
		color: var(--primary-text);
		font-size: 0.7rem;
		font-weight: 700;
		line-height: 1.25rem;
		text-align: center;
		font-variant-numeric: tabular-nums;
	}

	.badge.overdue {
		background: var(--danger);
		color: var(--danger-text);
	}

	.saved,
	.empty {
		color: var(--text-muted);
	}

	.group h3 {
		font-size: 0.95rem;
		margin: 0.75rem 0 0.25rem;
	}

	.count {
		color: var(--text-muted);
		font-weight: 400;
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.due-entry {
		display: flex;
		align-items: center;
		border-bottom: 1px solid var(--border);
	}

	.item-policy {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		min-height: var(--touch);
	}

	.due-row {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.25rem 0.5rem;
		min-height: var(--touch);
		padding: 0.25rem 0;
		color: var(--text);
		text-decoration: none;
	}

	.name {
		flex: 1;
		min-width: 0;
		font-weight: 600;
		overflow-wrap: anywhere;
	}

	.where,
	.when {
		color: var(--text-muted);
		font-size: 0.85rem;
		font-variant-numeric: tabular-nums;
	}

	/* The word says the status; the color repeats it. */
	.tag {
		font-size: 0.8rem;
		font-weight: 700;
	}

	.tag.danger {
		color: var(--danger);
	}

	.tag.warning {
		color: var(--warning);
	}
</style>
