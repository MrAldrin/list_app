<!--
	"Edit Item": name, description, quantity and date, saved together (or not at all).
	The date is optional: "Clear" removes it. Enter in the name field saves.
	Tags are chips that change at once, not on Save: one tag per item in single
	mode, several in multi mode.
	A muted line shows how often the item was added and when it was last added
	(it is not editable).
	The delete button deletes the item (with undo).
	It starts with the item as it was when the dialog opened; the save sends
	that version as `base_seq`.
-->
<script lang="ts">
	import { MAX_DESCRIPTION_LENGTH, MAX_NAME_LENGTH } from '#lib/ui/field-limits.ts';
	import { untrack } from 'svelte';
	import type { Item, TagSettings } from '#lib/data/index.ts';
	import FormDialog from '#lib/ui/FormDialog.svelte';
	import Icon from '#lib/ui/Icon.svelte';
	import { addedLabel, lastAddedLabel, stepQuantity } from './items';
	import { tagColor } from './tags';
	import { usableTimeZone } from './time-zone';

	let {
		item,
		itemTags,
		tags,
		tagSettings,
		canEdit,
		onSave,
		onTag,
		onDelete,
		onClose
	}: {
		item: Item;
		/** The item's tags now (not at opening): the chips save at once, so they follow the store. */
		itemTags: readonly string[];
		/** The list's tags, sorted. */
		tags: readonly string[];
		/** The tag colors, and the mode (one or several tags per item). */
		tagSettings: TagSettings;
		/** Whether shared-data writes are authorized. */
		canEdit: boolean;
		/** Saves the fields. The parent closes the dialog if it worked. */
		onSave: (changes: {
			name: string;
			description: string;
			quantity: number;
			date: string | null;
			due_time: string | null;
			due_timezone: string | null;
		}) => Promise<void>;
		/** Turns a tag on or off for the item at once. */
		onTag: (tag: string) => void;
		onDelete: () => void;
		onClose: () => void;
	} = $props();

	const lastAdded = $derived(lastAddedLabel(item.added_at));

	const nameId = $props.id();
	const descriptionId = `${nameId}-description`;
	const dateId = `${nameId}-date`;
	const tagsId = `${nameId}-tags`;
	// `untrack`: start with the values at opening; live changes by someone
	// else do not overwrite what is being typed.
	let name = $state(untrack(() => item.name));
	let description = $state(untrack(() => item.description));
	let quantity = $state(untrack(() => item.quantity));
	// '' means no date; the save sends null for it.
	let date = $state(untrack(() => item.date ?? ''));
	let dueTime = $state(untrack(() => item.due_time ?? ''));
	let dueTimezone = $state(untrack(() => item.due_timezone ?? ''));
	const unchangedDue = $derived(
		date === (item.date ?? '') &&
			dueTime === (item.due_time ?? '') &&
			dueTimezone === (item.due_timezone ?? '')
	);
	const validZone = $derived(usableTimeZone(dueTimezone) || (unchangedDue && !!item.due_at));
	const validDue = $derived(!date || !dueTime || validZone);
</script>

<FormDialog
	title="Edit Item"
	submitLabel="Save"
	submitDisabled={!canEdit || !validDue}
	focusBox
	onSubmit={() =>
		onSave({
			name,
			description,
			quantity,
			date: date || null,
			due_time: date && dueTime ? dueTime : null,
			due_timezone: date && dueTime ? dueTimezone.trim() : null
		})}
	{onClose}
>
	<label for={nameId}>Item Name</label>
	<input
		id={nameId}
		bind:value={name}
		maxlength={MAX_NAME_LENGTH}
		autocomplete="off"
		enterkeyhint="done"
	/>
	<label for={descriptionId}>Description / Notes</label>
	<textarea id={descriptionId} bind:value={description} maxlength={MAX_DESCRIPTION_LENGTH} rows="3"
	></textarea>
	<div class="quantity">
		<span id="{nameId}-quantity">Quantity</span>
		<div class="stepper" role="group" aria-labelledby="{nameId}-quantity">
			<button
				type="button"
				aria-label="Less"
				disabled={!canEdit || quantity <= 1}
				onclick={() => (quantity = stepQuantity(quantity, -1))}
			>
				<Icon name="remove" />
			</button>
			<output aria-live="polite">{quantity}</output>
			<button
				type="button"
				aria-label="More"
				disabled={!canEdit}
				onclick={() => (quantity = stepQuantity(quantity, 1))}
			>
				<Icon name="add" />
			</button>
		</div>
	</div>
	<label for={dateId}>Date</label>
	<div class="date-row">
		<input
			id={dateId}
			type="date"
			bind:value={date}
			onchange={() => {
				if (!date) {
					dueTime = '';
					dueTimezone = '';
				}
			}}
		/>
		<button
			type="button"
			disabled={!canEdit || !date}
			onclick={() => {
				date = '';
				dueTime = '';
				dueTimezone = '';
			}}
		>
			Clear
		</button>
	</div>
	{#if date}
		<label for="{nameId}-due-time">Due time (optional)</label>
		<input
			id="{nameId}-due-time"
			type="time"
			bind:value={dueTime}
			onchange={() => {
				if (!dueTime) dueTimezone = '';
			}}
		/>
		{#if dueTime}
			<label for="{nameId}-due-zone">Time zone (IANA, for example Europe/Oslo)</label>
			<input
				id="{nameId}-due-zone"
				bind:value={dueTimezone}
				autocomplete="off"
				aria-invalid={!validZone}
				aria-describedby={!validZone ? `${nameId}-zone-error` : undefined}
			/>
			{#if !validZone}
				<p id="{nameId}-zone-error" class="added" role="alert">
					Enter a valid IANA time zone, up to 64 characters, such as Europe/Oslo.
				</p>
			{/if}
			{#if unchangedDue && item.due_at}
				<p class="added">Server-confirmed UTC: {item.due_at}</p>
			{:else}
				<p class="added">Waiting to sync — the server will confirm the UTC time.</p>
			{/if}
		{/if}
	{/if}
	{#if tags.length > 0}
		<span id={tagsId} class="label">Tags</span>
		<ul class="chips" aria-labelledby={tagsId}>
			{#each tags as tag (tag)}
				{@const on = itemTags.includes(tag)}
				<li>
					<button
						class="chip"
						class:on
						style:--tag={tagColor(tagSettings, tag)}
						type="button"
						aria-pressed={on}
						disabled={!canEdit}
						onclick={() => onTag(tag)}
					>
						{tag}
					</button>
				</li>
			{/each}
		</ul>
		{#if tagSettings.mode === 'single'}
			<p class="added">One tag per item: a tap on another tag replaces this one.</p>
		{/if}
	{/if}
	<p class="added">{addedLabel(item.add_count)}</p>
	{#if lastAdded}
		<p class="added">{lastAdded}</p>
	{/if}
	{#snippet leading()}
		<button
			class="delete"
			type="button"
			aria-label="Delete Item"
			disabled={!canEdit}
			onclick={onDelete}
		>
			<Icon name="delete" />
		</button>
		<span class="spacer"></span>
	{/snippet}
</FormDialog>

<style>
	.quantity {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-left: 0.75rem;
		border: 1px solid var(--border);
		border-radius: var(--radius);
		font-weight: 600;
	}

	.stepper {
		display: flex;
		align-items: center;
	}

	.stepper button {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--primary);
	}

	output {
		min-width: 2rem;
		text-align: center;
		font-weight: 700;
	}

	.date-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.date-row input {
		flex: 1;
		min-width: 0;
	}

	.date-row button {
		min-height: var(--touch);
		padding: 0 0.5rem;
		color: var(--primary);
	}

	.label {
		font-weight: 600;
	}

	/* Wrapping chips, each a 44px tap area; the border shows the tag's color. */
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.chip {
		min-height: var(--touch);
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

	.added {
		margin: 0;
		color: var(--text-muted);
		font-size: 0.875rem;
	}

	.spacer {
		flex: 1;
	}

	.delete {
		padding: 0;
		display: grid;
		place-items: center;
		color: var(--danger);
	}
</style>
