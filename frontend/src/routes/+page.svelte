<script lang="ts">
	import ItemRow from '#lib/ItemRow.svelte';

	let listName: string = 'Groceries';
	let items = $state([
		{ id: '1', name: 'milk', done: false },
		{ id: '2', name: 'bread', done: false },
		{ id: '3', name: 'coffee', done: false }
	]);
	let itemCount = $derived(items.length);
	let itemWord = $derived(itemCount === 1 ? 'item' : 'items');
	let newName = $state('');
	let doneCount = $derived(items.filter((item) => item.done).length);

	function addItem() {
		if (newName.trim() === '') return;
		items.push({ id: crypto.randomUUID(), name: newName, done: false });
		newName = '';
	}

	function removeItem(id: string) {
		items = items.filter((item) => item.id !== id);
	}
</script>

<h1>{listName}</h1>
<p>{doneCount} of {itemCount} {itemWord} done</p>
{#if itemCount === 0}
	<p>Nothing on the list yet</p>
{:else}
	<ul>
		{#each items as item (item.id)}
			<ItemRow {item} onremove={() => removeItem(item.id)} />
		{/each}
	</ul>
{/if}

<input bind:value={newName} />
<button onclick={addItem}>Add</button>

<style>
	h1 {
		color: teal;
	}
</style>
