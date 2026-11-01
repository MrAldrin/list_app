<script lang="ts">
	let {
		label,
		open,
		onOpen
	}: {
		label: string;
		open: boolean;
		onOpen: () => void;
	} = $props();
</script>

<button
	class="option-dialog-row"
	type="button"
	aria-haspopup="dialog"
	aria-expanded={open}
	onclick={onOpen}
>
	<span>{label}</span>
	<span class="arrow" aria-hidden="true">›</span>
</button>

<style>
	.option-dialog-row {
		width: 100%;
		min-height: var(--touch);
		padding: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border: 0;
		border-top: 1px solid var(--border);
		border-radius: 0;
		background: transparent;
		color: inherit;
		font: inherit;
		font-weight: 500;
		text-align: left;
	}

	.arrow {
		color: var(--text-muted);
		font-size: 1.5rem;
	}
</style>
