<!--
	"Hide checked-off items": a switch, then a choice of mode, then the number
	for "After X days" or "Keep last X". Unlike the other options these are
	saved for the list, so every viewer sees the same. Each control sends only
	what it changed. A number is saved when the field loses focus (or on Enter).
-->
<script lang="ts">
	import type { HideDone } from '#lib/data/index.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import {
		COUNT_WARNING,
		HIDE_MODES,
		hideDoneChange,
		parseHideDoneCount,
		type HideDoneControl
	} from './hide-done';

	let {
		settings,
		onChange
	}: { settings: HideDone; onChange: (changes: Partial<HideDone>) => void } = $props();

	const enabled = $derived(settings.mode !== 'off');
	const nameId = $props.id();

	function change(control: HideDoneControl) {
		const changes = hideDoneChange(settings, control);
		if (changes) onChange(changes);
	}

	function commitCount(field: 'age_days' | 'recent_count', input: HTMLInputElement) {
		const value = parseHideDoneCount(input.value);
		if (value === null) {
			toasts.show(COUNT_WARNING, 'warning');
			input.value = String(settings[field]);
			return;
		}
		input.value = String(value);
		change({ field, value });
	}
</script>

<label class="row">
	<span>Hide checked-off items</span>
	<input
		type="checkbox"
		role="switch"
		checked={enabled}
		onchange={(event) => change({ field: 'enabled', value: event.currentTarget.checked })}
	/>
</label>

{#if enabled}
	<!-- Radio buttons: exactly one mode, like NiceGUI's toggle. -->
	<fieldset class="row sub">
		<legend class="visually-hidden">Hide mode</legend>
		<div class="modes">
			{#each HIDE_MODES as option (option.mode)}
				<label class:selected={settings.mode === option.mode}>
					<input
						class="visually-hidden"
						type="radio"
						name="hide-mode-{nameId}"
						value={option.mode}
						checked={settings.mode === option.mode}
						onchange={() => change({ field: 'mode', value: option.mode })}
					/>
					{option.label}
				</label>
			{/each}
		</div>
	</fieldset>

	{#if settings.mode === 'age' || settings.mode === 'recent'}
		{@const field = settings.mode === 'age' ? 'age_days' : 'recent_count'}
		<label class="row sub">
			<span>{settings.mode === 'age' ? 'Days before hiding' : 'Checked items to keep'}</span>
			<!-- `onchange` runs when the field loses focus or on Enter. -->
			<input
				class="count"
				type="number"
				inputmode="numeric"
				min="1"
				max="100000"
				step="1"
				value={settings[field]}
				onchange={(event) => commitCount(field, event.currentTarget)}
				onkeydown={(event) => {
					if (event.key === 'Enter') event.currentTarget.blur();
				}}
			/>
		</label>
	{/if}
{/if}

<style>
	.row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		min-height: var(--touch);
		border-top: 1px solid var(--border);
		font-weight: 500;
		cursor: pointer;
	}

	fieldset {
		margin: 0;
		padding: 0.25rem 0 0.25rem 0.75rem;
		border-left: none;
		border-right: none;
		border-bottom: none;
		cursor: default;
	}

	.sub {
		padding-left: 0.75rem;
		color: var(--text-muted);
	}

	/* A segmented control: three joined buttons, the chosen one filled. */
	.modes {
		display: flex;
		flex-wrap: wrap;
		border: 1px solid var(--primary);
		border-radius: var(--radius);
		overflow: hidden;
	}

	.modes label {
		display: grid;
		place-items: center;
		min-height: 2.25rem;
		padding: 0 0.75rem;
		color: var(--primary);
		font-weight: 500;
		cursor: pointer;
	}

	.modes label + label {
		border-left: 1px solid var(--primary);
	}

	.modes .selected {
		background: var(--primary);
		color: var(--primary-text);
	}

	.modes label:has(:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: -3px;
	}

	/* The chosen mode is filled with the focus color, so its ring takes the
	   text color instead. */
	.modes .selected:has(:focus-visible) {
		outline-color: var(--primary-text);
	}

	.count {
		width: 6rem;
		min-height: 2.25rem;
		text-align: right;
	}
</style>
