<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import type { RoomHandle } from '#lib/data/index.ts';
	import { ApiError, NetworkError } from '#lib/data/types.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import ReminderSettings from './ReminderSettings.svelte';
	import {
		ReminderApi,
		UnknownWriteOutcome,
		type Mode,
		type PendingWrite,
		type PolicyResult,
		type PolicyScope,
		type Preview
	} from './api';
	import {
		editStoredRule,
		editableRuleInput,
		validateEditableRules,
		type EditableRule
	} from './rule-edit';

	let {
		room,
		scope,
		uid,
		onClose
	}: { room: RoomHandle; scope: PolicyScope; uid?: string; onClose: () => void } = $props();
	const api = new ReminderApi(untrack(() => room.slug));
	const path = untrack(() =>
		scope === 'room'
			? 'policy'
			: `${scope === 'list' ? 'lists' : 'items'}/${encodeURIComponent(uid ?? '')}/policy`
	);
	let result = $state<PolicyResult | null>(null);
	let policyState = $state<'inherit' | 'off' | 'replace'>('replace');
	let preset = $state<Mode>('daily_summary');
	let summary = $state(false);
	let rules = $state<EditableRule[]>([]);
	let pending = $state<PendingWrite | null>(null);
	let busy = $state(false),
		loading = $state(true),
		conflict = $state(false),
		online = $state(true);
	let error = $state(''),
		notice = $state('');
	let shownPreview = $state<Preview | null>(null);
	let needsEnrollment = $state(false),
		settingsOpen = $state(false);
	const canSend = $derived(online && room.store.canWrite && !busy && !loading);
	function initialize(value: PolicyResult) {
		policyState = value.policy.state;
		preset = value.policy.preset ?? 'daily_summary';
		summary = value.policy.summary_enabled;
		rules = value.policy.rules.map(editStoredRule);
	}
	async function load(initial: boolean) {
		loading = true;
		error = '';
		try {
			const value = await api.policy(path);
			result = value;
			needsEnrollment = false;
			if (initial) initialize(value);
			else notice = 'Latest revision loaded. Your draft is unchanged; review it before saving.';
			conflict = false;
		} catch (e) {
			needsEnrollment = e instanceof ApiError && e.status === 403;
			error = needsEnrollment
				? 'Enrollment is unavailable. Explicitly enroll or resume to use private policies.'
				: e instanceof Error
					? e.message
					: 'Could not read policy.';
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		const update = () => (online = navigator.onLine);
		update();
		window.addEventListener('online', update);
		window.addEventListener('offline', update);
		void load(true);
		return () => {
			window.removeEventListener('online', update);
			window.removeEventListener('offline', update);
		};
	});
	function draft(): Record<string, unknown> {
		if (policyState !== 'replace') return { state: policyState };
		if (preset !== 'custom') return { state: policyState, preset };
		return {
			state: policyState,
			preset,
			summary_enabled: summary,
			rules: rules.map(editableRuleInput)
		};
	}
	$effect(() => {
		draft();
		shownPreview = null;
	});
	async function send() {
		if (!pending || !canSend) return;
		busy = true;
		error = '';
		notice = '';
		try {
			result = await api.sendPolicy(pending);
			initialize(result);
			pending = null;
			shownPreview = null;
			notice = 'Saved on this device.';
		} catch (e) {
			if (
				e instanceof UnknownWriteOutcome ||
				e instanceof NetworkError ||
				(e instanceof ApiError && e.status >= 500)
			)
				error = 'Result unknown. Retry the unchanged request; your draft is kept.';
			else {
				pending = null;
				conflict = e instanceof ApiError && e.code === 'revision_conflict';
				needsEnrollment = e instanceof ApiError && e.status === 403;
				error = conflict
					? 'Changed elsewhere. Load the latest revision and review your draft.'
					: e instanceof ApiError && e.status === 403
						? 'Enrollment is unavailable or expired. The previous request may have committed; open Personal reminders to explicitly enroll or resume. Your draft is kept.'
						: e instanceof Error
							? e.message
							: 'Could not save policy.';
			}
		} finally {
			busy = false;
		}
	}
	function save() {
		if (!result || pending || conflict || !canSend) return;
		const invalid =
			policyState === 'replace' && preset === 'custom' ? validateEditableRules(rules) : null;
		if (invalid) {
			error = invalid;
			return;
		}
		pending = api.prepare('PUT', path, { base_revision: result.policy.revision, ...draft() });
		void send();
	}
	async function showPreview() {
		if (!uid || scope !== 'item' || !canSend || pending) return;
		const invalid =
			policyState === 'replace' && preset === 'custom' ? validateEditableRules(rules) : null;
		if (invalid) {
			error = invalid;
			return;
		}
		busy = true;
		error = '';
		try {
			shownPreview = await api.preview(uid, draft());
		} catch (e) {
			error = e instanceof Error ? e.message : 'Could not preview.';
		} finally {
			busy = false;
		}
	}
</script>

<Dialog
	title="Personal {scope} reminders"
	onClose={() => {
		if (!pending && !busy) onClose();
	}}
	focusBox
>
	<p>Private to this browser. Reminder delivery is not active in phase 2.</p>
	<p>
		Item policies replace list policies; list policies replace the room policy. They are not
		combined.
	</p>
	{#if loading}<p role="status">Loading…</p>{/if}
	{#if error}<p role="alert">{error}</p>{/if}
	{#if notice}<p role="status">{notice}</p>{/if}
	{#if !online || !room.store.canWrite}<p>
			Connection required to save or preview. Your draft stays here while open.
		</p>{/if}
	{#if !loading && !result}<button type="button" disabled={!canSend} onclick={() => load(true)}
			>Try loading again</button
		>{/if}
	{#if needsEnrollment}<button type="button" onclick={() => (settingsOpen = true)}
			>Open enrollment settings</button
		>{/if}
	{#if conflict}<button type="button" disabled={!canSend} onclick={() => load(false)}
			>Load latest revision</button
		>{/if}
	{#if pending}<p>Retry the unchanged request before editing.</p>
		<button type="button" disabled={!canSend} onclick={send}>Retry request</button>{/if}
	{#if result}
		<p>
			Effective source: {result.effective.scope}; {result.effective.state}{result.effective.preset
				? ` (${result.effective.preset})`
				: ''}.
		</p>
		<fieldset disabled={busy || !!pending || conflict}>
			{#if scope !== 'room'}<label
					>Policy <select bind:value={policyState}
						><option value="inherit">Inherit parent (reset)</option><option value="off">Off</option
						><option value="replace">Replace parent</option></select
					></label
				>{/if}
			{#if policyState === 'replace'}
				<label
					>Schedule <select bind:value={preset}
						><option value="quiet">Quiet</option><option value="daily_summary">Daily summary</option
						><option value="scheduled">Scheduled</option><option value="custom">Custom</option
						></select
					></label
				>
				{#if preset === 'scheduled'}<p>One calendar day before and at due.</p>{/if}
				{#if preset === 'custom'}
					<label><input type="checkbox" bind:checked={summary} /> Include daily summary</label>
					{#each rules as rule, i (rule)}
						<div class="rule">
							<strong>Rule {i + 1}</strong>
							{#if rule.kind === 'relative'}
								<label
									>Amount before due <input
										type="number"
										min="0"
										step="1"
										bind:value={rule.amount}
									/></label
								>
								<label
									>Units <select bind:value={rule.unit}
										><option value="minutes">Elapsed minutes</option><option value="hours"
											>Elapsed hours</option
										><option value="days">Calendar days</option><option value="weeks"
											>Calendar weeks</option
										></select
									></label
								>
							{:else}
								<label>Wall date <input type="date" bind:value={rule.date} /></label><label
									>Wall time <input type="time" bind:value={rule.time} /></label
								><label>Time zone <input bind:value={rule.timezone} /></label>
								{#if rule.original && rule.date === rule.original.date && rule.time === rule.original.time && rule.timezone === rule.original.timezone}<p
									>
										Confirmed UTC: {rule.original.instant}
									</p>{:else}<p>New wall time must be in the future; server confirms UTC.</p>{/if}
							{/if}
							<button type="button" onclick={() => rules.splice(i, 1)}>Remove rule {i + 1}</button>
						</div>
					{/each}
					<button
						type="button"
						disabled={rules.length >= 5}
						onclick={() => rules.push({ kind: 'relative', amount: 1, unit: 'days' })}
						>Add relative rule</button
					>
					<button
						type="button"
						disabled={rules.length >= 5}
						onclick={() =>
							rules.push({
								kind: 'fixed',
								date: '',
								time: '',
								timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
							})}>Add fixed wall time</button
					>
				{/if}
			{/if}
			<button type="button" disabled={!canSend} onclick={save}>Save policy</button>
			{#if scope === 'item'}<button type="button" disabled={!canSend} onclick={showPreview}
					>Preview next five</button
				>{/if}
		</fieldset>
	{/if}
	{#if shownPreview}<section>
			<h3>Preview: {shownPreview.source} policy</h3>
			<p>
				Times are eligibility estimates, not a promise to send. Summary entries are this item's
				contribution, not the room total. Draft fixed IDs are provisional and not saved.
			</p>
			<p>
				Zone: {shownPreview.timezone}. Disabled reasons: {shownPreview.disabled_reasons.join(
					', '
				) || 'none'}.
			</p>
			<ul>
				{#each shownPreview.entries as entry, index (index)}<li>
						{entry.kind}: original UTC {entry.instant}{#if entry.deferred_until}; quiet-hours
							eligibility {entry.deferred_until}{/if}{#if entry.local_day}; summary day {entry.local_day}{/if}
					</li>{/each}
			</ul>
		</section>{/if}
	<button type="button" disabled={!!pending || busy} onclick={onClose}>Close</button>
</Dialog>
{#if settingsOpen}
	<ReminderSettings
		{room}
		onClose={() => {
			settingsOpen = false;
			void load(!result);
		}}
	/>
{/if}

<style>
	fieldset {
		display: grid;
		gap: 0.5rem;
		border: 0;
		padding: 0;
	}
	label {
		display: grid;
		gap: 0.2rem;
	}
	.rule {
		border: 1px solid var(--border);
		padding: 0.5rem;
		display: grid;
		gap: 0.4rem;
	}
</style>
