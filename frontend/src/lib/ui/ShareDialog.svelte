<!--
	"Share this list" / "Share this room": the link with a "Copy link" button.
	Shown when the device has no share sheet, as NiceGUI.
-->
<script lang="ts">
	import Dialog from './Dialog.svelte';
	import { copyLinkWithToast, shareMessage, type ShareKind } from './share.ts';

	let { kind, url, onClose }: { kind: ShareKind; url: string; onClose: () => void } = $props();

	let field = $state<HTMLInputElement>();

	const copy = () => copyLinkWithToast(url, field);
</script>

<Dialog title="Share this {kind}" {onClose} focusBox>
	<div class="body">
		<p class="muted">{shareMessage(kind)}</p>
		<input bind:this={field} type="text" readonly value={url} aria-label="Link" />
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
</style>
