// @vitest-environment happy-dom
import { flushSync, mount, unmount } from 'svelte';
import { expect, it, vi } from 'vitest';
import { makeItem, waitFor } from '#lib/data/test-helpers.ts';
import { reactive } from '#lib/test-support/reactive.svelte.ts';
import AddItem from './AddItem.svelte';

it('keeps selection by name across live props and never revives a removed name', async () => {
	const alpha = makeItem('list', { name: 'alpha' });
	const onAdd = vi.fn(async () => true);
	const props = reactive({ items: [alpha], canEdit: true, onAdd });
	const scroll = vi.spyOn(HTMLElement.prototype, 'scrollIntoView').mockImplementation(() => {});
	const target = document.createElement('div');
	document.body.append(target);
	const component = mount(AddItem, { target, props });
	const input = target.querySelector('input')!;
	const type = () => {
		input.focus();
		input.value = 'a';
		input.dispatchEvent(new Event('input', { bubbles: true }));
		flushSync();
	};
	const down = () => {
		input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
		flushSync();
	};
	const enter = () => {
		// happy-dom does not implement a key's default form submission.
		target.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
	};
	const selected = () => target.querySelector('[aria-selected="true"]');
	try {
		flushSync();
		type();
		down();
		expect(selected()?.textContent).toContain('alpha');
		props.items = [alpha, makeItem('list', { name: 'aardvark' })];
		flushSync();
		expect(
			[...target.querySelectorAll('[role="option"] span:first-child')].map((n) => n.textContent)
		).toEqual(['aardvark', 'alpha']);
		expect(selected()?.textContent).toContain('alpha');
		expect(input.getAttribute('aria-activedescendant')).toBe(selected()?.id);
		expect(scroll).toHaveBeenCalled();
		enter();
		await waitFor(() => expect(input.value).toBe(''));
		expect(onAdd).toHaveBeenLastCalledWith('alpha');

		type();
		down();
		down();
		expect(selected()?.textContent).toContain('alpha');
		props.items = props.items.map((item) =>
			item.uid === alpha.uid ? { ...item, name: 'zebra' } : item
		);
		flushSync();
		expect(selected()).toBeNull();
		expect(input.hasAttribute('aria-activedescendant')).toBe(false);
		props.items = props.items.map((item) => (item.uid === alpha.uid ? alpha : item));
		flushSync();
		expect(selected()).toBeNull();
		expect(input.hasAttribute('aria-activedescendant')).toBe(false);
		enter();
		await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(2));
		expect(onAdd).toHaveBeenLastCalledWith('a');
		await waitFor(() => expect(input.value).toBe(''));
	} finally {
		await unmount(component);
		target.remove();
		scroll.mockRestore();
	}
});
