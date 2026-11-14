import { flushSync } from 'svelte';
import { expect } from 'vitest';

export function button(target: ParentNode, name: string): HTMLButtonElement {
	const found = [...target.querySelectorAll<HTMLButtonElement>('button')].find((node) => {
		if (node.hasAttribute('aria-label')) return node.getAttribute('aria-label') === name;
		const copy = node.cloneNode(true) as HTMLElement;
		for (const hidden of copy.querySelectorAll('[aria-hidden="true"]')) hidden.remove();
		return copy.textContent?.trim() === name;
	});
	expect(found, `button ${name}`).toBeDefined();
	return found!;
}

export function click(target: ParentNode, name: string): void {
	const node = button(target, name);
	expect(node.disabled, name).toBe(false);
	node.click();
	flushSync();
}

export function fill(input: HTMLInputElement | HTMLTextAreaElement, value: string): void {
	input.value = value;
	input.dispatchEvent(new Event('input', { bubbles: true }));
	flushSync();
}

export function submit(target: ParentNode): void {
	const form = target.querySelector('form');
	expect(form).not.toBeNull();
	form!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
	flushSync();
}

export function rowNames(target: ParentNode): string[] {
	return [...target.querySelectorAll('ul.items button.name .text')].map(
		(node) => node.textContent ?? ''
	);
}
