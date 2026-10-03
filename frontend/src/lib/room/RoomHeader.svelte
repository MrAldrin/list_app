<!-- The top bar of the room page: app name, room name and the sign-out button. -->
<script lang="ts">
	let { name, onLogout }: { name: string; onLogout: () => void } = $props();
</script>

<header>
	<span class="brand" aria-hidden="true">List<b>R</b></span>
	<h1>{name}</h1>
	<button class="outline" type="button" onclick={onLogout}>Log out</button>
</header>

<style>
	header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 1rem;
	}

	.brand {
		font-size: 1.2rem;
		font-weight: 700;
	}

	.brand b {
		color: var(--primary);
		font-weight: 900;
	}

	h1 {
		flex: 1;
		min-width: 0;
		font-size: 1.5rem;
		/* Long room names end with "…" instead of breaking the layout. */
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
