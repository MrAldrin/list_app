<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import type { RoomHandle } from '#lib/data/index.ts';
	import { ApiError, NetworkError } from '#lib/data/types.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import { setDeviceZone } from './device-zone.svelte';
	import {
		ReminderApi,
		UnknownWriteOutcome,
		type Device,
		type Enrollment,
		type Mode,
		type PendingWrite
	} from './api';

	let { room, onClose }: { room: RoomHandle; onClose: () => void } = $props();
	const api = new ReminderApi(untrack(() => room.slug));
	const id = $props.id();
	let enrollment = $state<Enrollment | null>(null);
	let device = $state<Device | null>(null);
	let mode = $state<Mode>('daily_summary');
	let summary = $state('09:00');
	let timezone = $state('');
	let allDay = $state('09:00');
	let paused = $state(false);
	let quietEnabled = $state(true),
		quietStart = $state('22:00'),
		quietEnd = $state('08:00');
	let dailyCap = $state(10),
		spacingMinutes = $state(10);
	let contentPrivacy = $state<Device['content_privacy']>('generic');
	let repeatEnabled = $state(false),
		repeatDays = $state(1);
	let confirmZone = $state(false);
	let hasDeviceDraft = false;
	let recoveringIdentity = $state(false);
	let enrollmentValidationError: string | null = null;
	let previousOutcomeUnknown = false;
	let pendingOutcomeUnknown = false;
	let loading = $state(true);
	let busy = $state(false);
	let online = $state(true);
	let error = $state('');
	let notice = $state('');
	let conflict = $state(false);
	let pending = $state<PendingWrite | null>(null);
	let pendingKind = $state<'enroll' | 'room' | 'device' | 'optout' | null>(null);
	const canSend = $derived(online && room.store.canWrite && !busy && !loading);

	function applyEnrollment(value: Enrollment, initialize: boolean) {
		enrollment = value;
		if (value.state !== 'active') setDeviceZone(room, undefined);
		if (initialize) {
			mode = value.state === 'not_enrolled' ? 'daily_summary' : value.mode;
			summary = value.state === 'not_enrolled' ? '09:00' : value.summary_time;
		}
	}
	function applyDevice(value: Device | null, initialize: boolean) {
		device = value;
		if (value) hasDeviceDraft = true;
		if (initialize) {
			timezone = value?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? 'UTC';
			allDay = value?.all_day_time ?? '09:00';
			paused = value?.paused ?? false;
			quietEnabled = !!value?.quiet_hours;
			quietStart = value?.quiet_hours?.start ?? '22:00';
			quietEnd = value?.quiet_hours?.end ?? '08:00';
			dailyCap = value?.daily_cap ?? 10;
			spacingMinutes = value?.spacing_minutes ?? 10;
			contentPrivacy = value?.content_privacy ?? 'generic';
			repeatEnabled = value?.overdue_repeat_days != null;
			repeatDays = value?.overdue_repeat_days ?? 1;
		}
	}
	async function load(initialize: boolean) {
		loading = true;
		error = '';
		try {
			const [a, b] = await Promise.all([api.enrollment(), api.device()]);
			applyEnrollment(a.enrollment, initialize);
			applyDevice(b.device, initialize);
			conflict = false;
			recoveringIdentity = false;
			if (enrollmentValidationError !== null) {
				const unknown = previousOutcomeUnknown
					? ' The previous request may have committed and cannot be replayed on a new installation.'
					: '';
				error =
					b.device === null
						? `This device enrollment is unavailable or expired.${unknown} Your edits are kept. Explicitly enroll to continue.`
						: `${enrollmentValidationError}${previousOutcomeUnknown ? ' The previous request may have committed; review the current settings before trying again.' : ''}`;
				enrollmentValidationError = null;
				previousOutcomeUnknown = false;
			}
			if (!initialize)
				notice = 'Latest revisions loaded. Your edits remain; review them before saving.';
		} catch (e) {
			if (enrollmentValidationError !== null) {
				error = `Could not check device identity. Try loading again. ${enrollmentValidationError}${previousOutcomeUnknown ? ' The previous request may have committed; it cannot be replayed on a new installation.' : ''}`;
			} else {
				error = e instanceof Error ? e.message : 'Could not load settings.';
			}
		} finally {
			loading = false;
		}
	}
	onMount(() => {
		const update = () => {
			online = navigator.onLine;
		};
		update();
		window.addEventListener('online', update);
		window.addEventListener('offline', update);
		void load(true);
		return () => {
			window.removeEventListener('online', update);
			window.removeEventListener('offline', update);
		};
	});
	async function send() {
		if (!pending || !pendingKind || !canSend) return;
		const write = pending;
		busy = true;
		error = '';
		notice = '';
		try {
			if (pendingKind === 'device') {
				const result = await api.sendDevice(pending);
				applyDevice(result, true);
				if (enrollment?.state === 'active') setDeviceZone(room, result.timezone);
				confirmZone = false;
			} else {
				const result = await api.sendEnrollment(pending);
				applyEnrollment(result, false);
				if (result.state !== 'active') setDeviceZone(room, undefined);
				if (pendingKind === 'enroll') {
					// Enrollment may have created the device; this GET does not renew it.
					try {
						const latest = (await api.device()).device;
						applyDevice(latest, !hasDeviceDraft);
						if (result.state === 'active') setDeviceZone(room, latest?.timezone);
					} catch {
						notice = 'Enrolled. Reopen settings to load device settings.';
					}
				}
			}
			pending = null;
			pendingKind = null;
			pendingOutcomeUnknown = false;
			if (!notice) notice = 'Saved on this device.';
		} catch (e) {
			if (
				e instanceof UnknownWriteOutcome ||
				e instanceof NetworkError ||
				(e instanceof ApiError && e.status >= 500)
			) {
				pendingOutcomeUnknown = true;
				error =
					'The result is unknown. Retry the same request when connected; your edits are kept.';
			} else if (
				pendingKind === 'enroll' &&
				!('timezone' in write.body) &&
				e instanceof ApiError &&
				e.status === 422 &&
				e.code === 'invalid_request'
			) {
				// An existing installation may have expired before enrollment; verify before diagnosing it.
				enrollmentValidationError = e.message;
				previousOutcomeUnknown = pendingOutcomeUnknown;
				pending = null;
				pendingKind = null;
				pendingOutcomeUnknown = false;
				recoveringIdentity = true;
				enrollment = null;
				device = null;
				await load(false);
			} else if (e instanceof ApiError && e.status === 403 && e.code === 'not_enrolled') {
				pending = null;
				pendingKind = null;
				// The old request cannot be replayed against a different installation.
				recoveringIdentity = true;
				enrollment = null;
				device = null;
				await load(false);
				error =
					'This device enrollment is unavailable or expired. The previous request may have committed; it cannot be retried on a new installation. Your edits are kept. Check the status and explicitly enroll to continue.';
			} else {
				pending = null;
				pendingKind = null;
				conflict = e instanceof ApiError && e.code === 'revision_conflict';
				error = conflict
					? 'Settings changed elsewhere. Load latest revisions and review your edits.'
					: e instanceof Error
						? e.message
						: 'Could not save settings.';
			}
		} finally {
			busy = false;
		}
	}
	function start(kind: 'enroll' | 'room' | 'device' | 'optout') {
		if (!canSend || pending || conflict || !enrollment) return;
		pendingOutcomeUnknown = false;
		if (kind === 'enroll') {
			pending = api.prepare('POST', 'enrollment', {
				base_revision: enrollment.revision,
				...(device ? {} : { timezone }),
				mode,
				summary_time: summary
			});
		} else if (kind === 'room') {
			pending = api.prepare('PATCH', 'preferences', {
				base_revision: enrollment.revision,
				mode,
				summary_time: summary
			});
		} else if (kind === 'optout') {
			pending = api.prepare('PATCH', 'preferences', {
				base_revision: enrollment.revision,
				opted_out: true
			});
		} else if (device) {
			if (timezone !== device.timezone && !confirmZone) {
				error = 'Confirm the time zone change first.';
				return;
			}
			if (
				(quietEnabled && (!quietStart || !quietEnd || quietStart === quietEnd)) ||
				!Number.isInteger(dailyCap) ||
				dailyCap < 1 ||
				dailyCap > 50 ||
				!Number.isInteger(spacingMinutes) ||
				spacingMinutes < 1 ||
				spacingMinutes > 60 ||
				(repeatEnabled && (!Number.isInteger(repeatDays) || repeatDays < 1 || repeatDays > 30))
			) {
				error =
					'Quiet hours need different start and end times. Daily cap must be 1–50, spacing 1–60 minutes, and overdue repeat 1–30 days; use whole numbers.';
				return;
			}
			pending = api.prepare('PATCH', 'preferences/device', {
				base_revision: device.revision,
				timezone,
				all_day_time: allDay,
				paused,
				quiet_hours: quietEnabled ? { start: quietStart, end: quietEnd } : null,
				daily_cap: dailyCap,
				spacing_minutes: spacingMinutes,
				content_privacy: contentPrivacy,
				overdue_repeat_days: repeatEnabled ? repeatDays : null
			});
		} else return;
		pendingKind = kind;
		void send();
	}
</script>

<Dialog
	title="Personal reminders"
	onClose={() => {
		if (!pending && !busy) onClose();
	}}
	focusBox
>
	<p>
		Private to this browser. Room settings apply only here; device settings apply across enrolled
		rooms. Reminder delivery is not active in phase 2.
	</p>
	<p>Due views use the device time zone when enrolled, otherwise the browser time zone.</p>
	{#if loading}<p role="status">Loading settings…</p>{/if}
	{#if error}<p role="alert">{error}</p>{/if}
	{#if notice}<p role="status">{notice}</p>{/if}
	{#if !online || !room.store.canWrite}<p>
			Connection required. Your edits stay here while this dialog is open.
		</p>{/if}
	{#if !loading && !enrollment}
		<button type="button" disabled={!online} onclick={() => load(!recoveringIdentity)}
			>Try loading again</button
		>
	{/if}
	{#if conflict}<button type="button" disabled={!canSend} onclick={() => load(false)}
			>Load latest revisions</button
		>{/if}
	{#if pending}<p>Retry the unchanged request before making more changes.</p>
		<button type="button" disabled={!canSend} onclick={send}>Retry request</button>{/if}
	{#if enrollment}
		<fieldset disabled={busy || !!pending || conflict}>
			<p>
				Status: {enrollment.state === 'not_enrolled'
					? 'Not enrolled'
					: enrollment.state === 'needs_resume'
						? 'Needs resume'
						: enrollment.state === 'opted_out'
							? 'Opted out'
							: 'Active'}
			</p>
			{#if enrollment.state === 'needs_resume' || enrollment.state === 'opted_out'}<p>
					Only an explicit resume restores this room's grant.
				</p>{/if}
			<label for="{id}-mode">Room reminder mode</label>
			<select id="{id}-mode" bind:value={mode}>
				<option value="quiet">Quiet</option><option value="daily_summary">Daily summary</option
				><option value="scheduled">Scheduled</option><option value="custom">Custom</option>
			</select>
			<label for="{id}-summary">Room summary time</label><input
				id="{id}-summary"
				type="time"
				bind:value={summary}
			/>
			{#if enrollment.state === 'not_enrolled' || enrollment.state === 'needs_resume' || enrollment.state === 'opted_out'}
				{#if !device}<label for="{id}-initial-zone">Time zone for this device</label><input
						id="{id}-initial-zone"
						bind:value={timezone}
					/>{/if}
				<button type="button" disabled={!canSend} onclick={() => start('enroll')}
					>{enrollment.state === 'not_enrolled' ? 'Enroll this device' : 'Resume this room'}</button
				>
			{:else}
				<button type="button" disabled={!canSend} onclick={() => start('room')}
					>Save room settings</button
				>
				<button type="button" disabled={!canSend} onclick={() => start('optout')}
					>Opt out of this room</button
				>
			{/if}
			{#if device}
				<h3>Device settings</h3>
				<p>These apply to every room enrolled on this device.</p>
				<label for="{id}-zone">Device time zone</label><input
					id="{id}-zone"
					bind:value={timezone}
				/>
				{#if timezone !== device.timezone}<label
						><input type="checkbox" bind:checked={confirmZone} /> Confirm time zone change for all enrolled
						rooms</label
					>{/if}
				<label for="{id}-all-day">All-day reminder time</label><input
					id="{id}-all-day"
					type="time"
					bind:value={allDay}
				/>
				<label><input type="checkbox" bind:checked={paused} /> Pause reminders on this device</label
				>
				<label><input type="checkbox" bind:checked={quietEnabled} /> Enable quiet hours</label>
				{#if quietEnabled}
					<label for="{id}-quiet-start">Quiet hours start</label>
					<input id="{id}-quiet-start" type="time" bind:value={quietStart} />
					<label for="{id}-quiet-end">Quiet hours end</label>
					<input id="{id}-quiet-end" type="time" bind:value={quietEnd} />
				{/if}
				<label for="{id}-daily-cap">Daily cap (1–50)</label>
				<input id="{id}-daily-cap" type="number" min="1" max="50" step="1" bind:value={dailyCap} />
				<label for="{id}-spacing">Minimum spacing in minutes (1–60)</label>
				<input
					id="{id}-spacing"
					type="number"
					min="1"
					max="60"
					step="1"
					bind:value={spacingMinutes}
				/>
				<label for="{id}-privacy">Notification content privacy</label>
				<select id="{id}-privacy" bind:value={contentPrivacy}>
					<option value="generic">Generic</option>
					<option value="counts">Counts</option>
					<option value="names">Names</option>
				</select>
				<label><input type="checkbox" bind:checked={repeatEnabled} /> Enable overdue repeat</label>
				{#if repeatEnabled}
					<label for="{id}-repeat">Overdue repeat interval in days (1–30)</label>
					<input id="{id}-repeat" type="number" min="1" max="30" step="1" bind:value={repeatDays} />
				{/if}
				<button type="button" disabled={!canSend} onclick={() => start('device')}
					>Save device settings</button
				>
			{/if}
		</fieldset>
	{/if}
	<div class="actions">
		<button type="button" disabled={!!pending || busy} onclick={onClose}>Close</button>
	</div>
</Dialog>

<style>
	fieldset {
		border: 0;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}
	p {
		margin: 0.5rem 0;
	}
</style>
