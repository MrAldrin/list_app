<!--
	Changes that did not reach the server (docs/background/offline-editing-details.md, "Not saved"). A
	banner shows the count; "Review" opens a sheet with what and why:

	- Not saved: a change refused or failed after it waited (made offline, or
	  answered late). Dismiss; "Save mine anyway" for a change someone else
	  changed meanwhile.
	- Changes waiting after sign-out stay in this device's room queue until the
	  user chooses Send or Discard.
	- Old changes not sent yet: held for 30 days (R10). Sending could apply them
	  twice if the server no longer remembers an earlier answer.
	- Changes this version cannot read (R13). Discard each.

	When access is gone (R9), the banner says so instead: sign in again, or
	discard. Not-saved rejections are stored with this room's device-local queue.
-->
<script lang="ts">
	import {
		cantBeSentText,
		describeChange,
		notSavedCountText,
		type RoomHandle,
		type SentOp
	} from '#lib/data/index.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let { room }: { room: RoomHandle } = $props();

	let sheet = $state(false);
	/** Everything the user may need to look at (the banner's count). */
	const attention = $derived(
		room.store.notSaved.length +
			room.heldOps.length +
			room.signoutHeldOps.length +
			room.unreadableOps.length
	);
	const waiting = $derived(room.waitingCount);

	/** The name the user sees for an op's item or list, when the page has it. */
	function nameOf(op: SentOp): string | null {
		if ('item_uid' in op) return room.store.item(op.item_uid)?.name ?? null;
		if ('list_uid' in op) return room.store.list(op.list_uid)?.name ?? null;
		return null;
	}

	async function saveAnyway(id: number) {
		const result = await room.saveMineAnyway(id);
		if (!result.ok) toasts.show(result.message, 'warning');
	}

	/** The room sign-in prompt sits under the banner: focus its field. */
	function signIn() {
		document.getElementById('room-password')?.focus();
	}
</script>

{#if room.accessLost}
	<div class="card banner" role="status">
		<span>{cantBeSentText(waiting, room.isShare)}</span>
		<div class="actions">
			{#if !room.isShare}
				<button type="button" onclick={signIn}>Sign in</button>
			{/if}
			<button type="button" onclick={() => room.discardWaiting()}>Discard all</button>
		</div>
	</div>
{:else if attention > 0}
	<div class="card banner" role="status">
		<span>
			{#if room.signoutHeldOps.length > 0}
				{room.signoutHeldOps.length === 1
					? "1 change is held in this room's queue on this device."
					: `${room.signoutHeldOps.length} changes are held in this room's queue on this device.`}
			{:else}
				{notSavedCountText(attention)}
			{/if}
		</span>
		<button type="button" onclick={() => (sheet = true)}>Review</button>
	</div>
{/if}

{#if sheet && attention > 0}
	<Dialog title="Changes not saved" onClose={() => (sheet = false)}>
		{#if room.store.notSaved.length > 0}
			<section>
				<h3>Not saved</h3>
				<ul>
					{#each room.store.notSaved as change (change.id)}
						<li>
							<p>{change.text}</p>
							<div class="actions">
								<button type="button" onclick={() => room.store.dismissNotSaved(change.id)}>
									Dismiss
								</button>
								{#if change.code === 'changed_meanwhile'}
									<button type="button" class="primary" onclick={() => saveAnyway(change.id)}>
										Save mine anyway
									</button>
								{/if}
							</div>
						</li>
					{/each}
				</ul>
				<div class="actions">
					<button type="button" onclick={() => room.store.dismissAllNotSaved()}>Dismiss all</button>
				</div>
			</section>
		{/if}

		{#if room.signoutHeldOps.length > 0}
			<section>
				<h3>Changes held after sign-out</h3>
				<p class="muted">
					These are in this room's queue on this device. They are not sent until you choose. Changes
					more than 30 days old stay held and need a separate choice.
				</p>
				<ul>
					{#each room.signoutHeldOps as held (held.opId)}
						<li>
							<span>{describeChange(held.op, nameOf(held.op))}</span>
							<button type="button" onclick={() => room.discard(held.opId)}>Discard</button>
						</li>
					{/each}
				</ul>
				<div class="actions">
					<button type="button" class="primary" onclick={() => room.sendAfterSignIn()}>
						Send changes
					</button>
				</div>
			</section>
		{/if}

		{#if room.heldOps.length > 0}
			<section>
				<h3>Old changes not sent yet</h3>
				<p class="muted">
					These are in this room's queue on this device and were made more than 30 days ago. The
					server may no longer remember an earlier answer, so sending could apply them twice. They
					are sent only when you choose.
				</p>
				<ul>
					{#each room.heldOps as held (held.opId)}
						<li>
							<span>{describeChange(held.op, nameOf(held.op))}</span>
							<button type="button" onclick={() => room.discard(held.opId)}>Discard</button>
						</li>
					{/each}
				</ul>
				<div class="actions">
					<button type="button" class="primary" onclick={() => room.sendHeld()}>Send all</button>
				</div>
			</section>
		{/if}

		{#if room.unreadableOps.length > 0}
			<section>
				<h3>Changes this version cannot read</h3>
				<ul>
					{#each room.unreadableOps as unreadable (unreadable.opId)}
						<li>
							<span>
								{unreadable.reason === 'newer_format'
									? 'Made by a newer version of this app.'
									: 'Could not be read.'}
							</span>
							<button type="button" onclick={() => room.discard(unreadable.opId)}>Discard</button>
						</li>
					{/each}
				</ul>
			</section>
		{/if}
	</Dialog>
{/if}

<style>
	.banner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 0.75rem;
		margin-bottom: 1rem;
		padding: 0.6rem 0.75rem;
		border-left: 3px solid var(--warning);
	}

	.banner .actions {
		gap: 0.5rem;
	}

	h3 {
		font-size: 1rem;
		margin: 1rem 0 0.25rem;
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	li {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border);
	}

	li p {
		margin: 0;
	}

	section .actions {
		margin-top: 0.5rem;
	}

	.muted {
		font-size: 0.9rem;
	}
</style>
