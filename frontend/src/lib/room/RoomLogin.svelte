<!--
	The room password prompt. The password only lives in this field until it is
	sent; the server answers with an HTTP-only cookie that JavaScript never sees.
-->
<script lang="ts">
	import type { ActionResult } from '#lib/data/index.ts';
	import PasswordPrompt from '#lib/ui/PasswordPrompt.svelte';

	// `$props()` lists what the parent passes in: <RoomLogin onLogin={…} />.
	let { onLogin }: { onLogin: (password: string) => Promise<ActionResult<unknown>> } = $props();
</script>

<PasswordPrompt
	title="Enter Room Password"
	label="Room Password"
	inputId="room-password"
	errorId="password-error"
	buttonText="Enter"
	onSubmit={onLogin}
/>
