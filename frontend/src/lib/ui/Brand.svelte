<!--
	The app name, "ListR" with a bold, colored R. It is decorative (aria-hidden):
	the page's heading or title names the app. `size` sets the font size; the
	top bars use the default, the admin page a larger one.
-->
<script lang="ts">
	let { size = '1.2rem' }: { size?: string } = $props();
</script>

<span class="brand" style:font-size={size} aria-hidden="true">List<b>R</b></span>

<style>
	.brand {
		font-weight: 700;
	}

	.brand b {
		color: var(--primary);
		font-weight: 900;
	}
</style>
