<!--
	"Room invitations" on the admin page (NiceGUI's `invitation_controls`).
	"Generate 7-day invitation" issues a link that anyone can use to create a
	room; its link shows once, in a dialog. Active invitations get "Revoke".
	The server checks admin sign-in on every request.
-->
<script lang="ts">
	import { admin, type Invitation, type IssuedInvitation } from '#lib/data/index.ts';
	import LoadError from '#lib/ui/LoadError.svelte';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import InvitationDialog from './InvitationDialog.svelte';
	import { formatUtc, statusLabel } from './invitations.ts';

	let { onSignedOut }: { onSignedOut: () => void } = $props();

	let invitations = $state.raw<Invitation[] | null>(null);
	let error = $state('');
	let busy = $state(false);
	let issued = $state.raw<IssuedInvitation | null>(null);

	/** Shows a failed answer as a toast; a lost admin sign-in shows the sign-in prompt. */
	function handleFailure(result: { ok: false; code: string; message: string }) {
		toasts.show(result.message, 'warning');
		if (admin.isSignedOut(result)) {
			issued = null;
			onSignedOut();
		}
	}

	async function load() {
		const result = await admin.invitations();
		if (result.ok) {
			invitations = result.result;
			error = '';
			return;
		}
		if (admin.isSignedOut(result)) {
			handleFailure(result);
			return;
		}
		error = result.message;
	}

	$effect(() => {
		void load();
	});

	async function generate() {
		if (busy) return;
		busy = true;
		const result = await admin.issueInvitation();
		busy = false;
		if (!result.ok) {
			handleFailure(result);
			return;
		}
		issued = result.result;
		void load();
	}

	async function revoke(invitation: Invitation) {
		if (busy) return;
		busy = true;
		const result = await admin.revokeInvitation(invitation.id);
		busy = false;
		if (!result.ok) {
			handleFailure(result);
			return;
		}
		void load();
	}
</script>

<section aria-labelledby="invitations-title">
	<h2 id="invitations-title">Room invitations</h2>
	<p class="muted">Reusable for 7 days. Anyone with the link can create a room.</p>
	<button class="primary generate" type="button" disabled={busy} onclick={generate}>
		Generate 7-day invitation
	</button>

	{#if error}
		<LoadError title="Could not load the invitations." detail={error} onRetry={load} />
	{/if}

	{#if invitations === null}
		{#if !error}<p class="muted">Loading…</p>{/if}
	{:else if invitations.length > 0}
		<ul>
			{#each invitations as invitation (invitation.id)}
				<li class="card">
					<div>
						<p class="title">Invitation #{invitation.id}: {statusLabel(invitation.status)}</p>
						<p class="time">Created {formatUtc(invitation.created_at)}</p>
						<p class="time">Expires {formatUtc(invitation.expires_at)}</p>
					</div>
					{#if invitation.status === 'active'}
						<button
							class="revoke"
							type="button"
							disabled={busy}
							aria-label="Revoke invitation #{invitation.id}"
							onclick={() => revoke(invitation)}
						>
							Revoke
						</button>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>

{#if issued}
	<InvitationDialog {issued} onClose={() => (issued = null)} />
{/if}

<style>
	section {
		margin-top: 1.5rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border);
		display: grid;
		gap: 0.5rem;
	}

	h2 {
		font-size: 1.15rem;
	}

	.muted {
		font-size: 0.9rem;
	}

	.generate {
		width: 100%;
	}

	ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.5rem;
	}

	li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
	}

	.title {
		font-weight: 600;
	}

	.time {
		font-size: 0.8rem;
		color: var(--text-muted);
	}

	.revoke {
		color: var(--danger);
		font-weight: 600;
	}
</style>
