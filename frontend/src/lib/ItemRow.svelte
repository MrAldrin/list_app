<script lang="ts">
	type Item = { id: string; name: string; done: boolean };
	let { item, onremove }: { item: Item; onremove: () => void } = $props();
</script>

<li>
	<input type="checkbox" bind:checked={item.done} />
	{item.name}{item.naem} <button onclick={onremove}>x</button>
</li>
