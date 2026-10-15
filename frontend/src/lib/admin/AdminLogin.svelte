<!--
	The admin sign-in (NiceGUI's /admin/login). The password is the app
	password (APP_PASSWORD). It only lives in this field until it is sent; the
	server remembers the sign-in for this browser, not the password.
-->
<script lang="ts">
	import { admin } from '#lib/data/index.ts';
	import PasswordPrompt from '#lib/ui/PasswordPrompt.svelte';

	let { onSignedIn }: { onSignedIn: () => void } = $props();

	async function login(password: string) {
		const result = await admin.login(password);
		if (result.ok) onSignedIn();
		return result;
	}
</script>

<PasswordPrompt
	title="Enter Admin Password"
	label="Admin Password"
	inputId="admin-password"
	errorId="admin-password-error"
	buttonText="Log in"
	onSubmit={login}
/>
