<!--
	A small dot next to an item or a list with a change that is not sent yet.
	Outside the name button, so the name keeps its accessible name.
-->
<span class="unsent" role="img" aria-label="Not sent yet"></span>

<style>
	.unsent {
		display: inline-block;
		width: 0.5rem;
		height: 0.5rem;
		flex-shrink: 0;
		border-radius: 50%;
		background: var(--warning);
	}
</style>
