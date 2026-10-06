<!--
	The list menu (the ⋮ button in the list header), as NiceGUI's: "Share List"
	for everyone who sees the list, and "Reset share link" for room members
	only. A share link opens this list without the room password; resetting
	it stops the old link for everyone.
-->
<script lang="ts">
	import { resolve } from '$app/paths';
	import type { List, RoomHandle } from '#lib/data/index.ts';
	import ConfirmDialog from '#lib/ui/ConfirmDialog.svelte';
	import MenuButton from '#lib/ui/MenuButton.svelte';
	import ShareDialog from '#lib/ui/ShareDialog.svelte';
	import { absoluteUrl, shareNatively } from '#lib/ui/share.ts';
	import { toasts } from '#lib/ui/toasts.svelte.ts';

	let {
		room,
		list,
		canReset,
		onReset
	}: {
		room: RoomHandle;
		list: Pick<List, 'uid'>;
		/** Room members may reset the link; share-link visitors may not. */
		canReset: boolean;
		/** Called with the new token after a reset (a share page follows it). */
		onReset?: (token: string) => void;
	} = $props();

	let dialog = $state<'share' | 'reset' | null>(null);
	let shareUrl = $state('');
	/** The token read when the menu opened (it may change elsewhere). */
	let token = $state<string | null>(null);

	async function loadToken(): Promise<string | null> {
		const result = await room.shareLink(list);
		if (!result.ok) {
			toasts.show(result.message, 'warning');
			return null;
		}
		token = result.result.token;
		return token;
	}

	// Read the token as the menu opens, so "Share List" can open the phone's
	// share sheet at once: browsers allow it only right after a tap.
	function menuOpened() {
		token = null;
		void room.shareLink(list).then((result) => {
			if (result.ok) token = result.result.token;
		});
	}

	async function share(close: () => void) {
		close();
		const current = token ?? (await loadToken());
		if (!current) return;
		const url = absoluteUrl(resolve('/share/[token]', { token: current }));
		if ((await shareNatively('list', url)) !== 'fallback') return;
		shareUrl = url;
		dialog = 'share';
	}

	function askReset(close: () => void) {
		close();
		dialog = 'reset';
	}

	async function reset() {
		const result = await room.resetShareLink(list);
		if (result.ok) {
			token = result.result.token;
			dialog = null;
			toasts.show('Share link reset', 'success');
			onReset?.(result.result.token);
			return;
		}
		toasts.show(result.message, 'warning');
		// No access or no list: nothing to retry. Busy or offline: try again.
		if (result.code !== 'unavailable' && result.code !== 'network') dialog = null;
	}
</script>

<MenuButton label="List menu" onOpen={menuOpened}>
	{#snippet children(close)}
		<button type="button" onclick={() => share(close)}>Share List</button>
		{#if canReset}
			<button type="button" onclick={() => askReset(close)}>Reset share link</button>
		{/if}
	{/snippet}
</MenuButton>

{#if dialog === 'share'}
	<ShareDialog kind="list" url={shareUrl} onClose={() => (dialog = null)} />
{:else if dialog === 'reset'}
	<ConfirmDialog
		question="Reset share link?"
		detail="Everyone using the old link will lose access. Room access stays unchanged."
		confirmLabel="Reset share link"
		onConfirm={reset}
		onClose={() => (dialog = null)}
	/>
{/if}
