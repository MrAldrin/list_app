<!--
	"Add ListR to your home screen": the manual install steps from the room
	menu. Texts as NiceGUI's install help (`src/ui/install_help.py`). It only
	explains; it changes nothing. The room page's manifest makes a new icon
	open this room (see manifest.ts).
-->
<script lang="ts">
	import Dialog from '#lib/ui/Dialog.svelte';

	let { onClose }: { onClose: () => void } = $props();
</script>

<Dialog title="Add ListR to your home screen" {onClose} focusBox>
	<div class="body">
		<p>Open ListR from your home screen, like an app.</p>
		<p>Open your room and sign in first.</p>

		<h3>iPhone/iPad — Safari recommended</h3>
		<ol>
			<li>Tap <b>Share</b> (you may find it inside the menu).</li>
			<li>Choose <b>Add to Home Screen</b>.</li>
			<li>Enable <b>Open as Web App</b>, if shown.</li>
			<li>Tap <b>Add</b>.</li>
		</ol>

		<h3>Android — Chrome recommended</h3>
		<ol>
			<li>Open the <b>⋮ menu</b>.</li>
			<li>Tap <b>Add to Home screen</b> or <b>Install app</b>.</li>
			<li>Follow the prompts to confirm.</li>
		</ol>

		<h3>Using another browser?</h3>
		<p>
			You can also use ListR in other modern browsers. Installation options and button names may
			differ. If you can't find the option, try Safari on iPhone/iPad or Chrome on Android.
		</p>
		<p>
			For a room-specific launch, install while viewing your room, not a list. New installations
			from a room are configured to open that room. You may need its password the first time. Keep
			your room link handy as a fallback.
		</p>
		<p>
			ListR keeps one app identity: switching rooms does not retarget your icon, and your browser
			may reuse an existing installation. Older icons may still open your last-used room or ask for
			a room link; they may not update automatically. Save your room link and password before
			removing or reinstalling an old icon.
		</p>
		<div class="actions">
			<button type="button" onclick={onClose}>Close</button>
		</div>
	</div>
</Dialog>

<style>
	.body {
		display: grid;
		gap: 0.5rem;
		/* Long help on a short phone screen scrolls inside the dialog. */
		max-height: calc(100dvh - 8rem);
		overflow-y: auto;
	}

	h3 {
		font-size: 1rem;
		margin: 0.5rem 0 0;
	}

	ol {
		margin: 0;
		padding-left: 1.5rem;
	}

	.actions {
		display: flex;
		justify-content: flex-end;
	}
</style>
