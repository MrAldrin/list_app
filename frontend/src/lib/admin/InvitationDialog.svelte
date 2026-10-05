<!--
	A new invitation's link (NiceGUI's dialog after "Generate 7-day
	invitation"). The server sends the token only once, so this is the only
	time the link can be seen: save it now.
-->
<script lang="ts">
	import type { IssuedInvitation } from '#lib/data/index.ts';
	import Dialog from '#lib/ui/Dialog.svelte';
	import { copyText } from '#lib/ui/share.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';
	import { invitationUrl } from './invitations.ts';

	let { issued, onClose }: { issued: IssuedInvitation; onClose: () => void } = $props();

	const id = $props.id();
	const url = $derived(invitationUrl(issued.token));
	let field = $state<HTMLInputElement>();

	async function copy() {
		if (await copyText(url, field)) toasts.show('Link copied', 'success');
		else toasts.show('Could not copy. Select the link and copy it.', 'warning');
	}
</script>

<Dialog title="Invitation #{issued.invitation.id}" {onClose} focusBox>
	<div class="body">
		<p>Save this link now. It is only shown once and expires in 7 days.</p>
		<label for="{id}-link">Invitation link</label>
		<input id="{id}-link" bind:this={field} type="text" readonly value={url} />
		<div class="actions">
			<button type="button" onclick={onClose}>Close</button>
			<button class="primary" type="button" onclick={copy}>Copy link</button>
		</div>
	</div>
</Dialog>

<style>
	.body {
		display: grid;
		gap: var(--gap);
	}

	label {
		font-weight: 600;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
</style>
