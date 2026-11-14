// Reactive inputs for mounted tests. No application code imports this file.
export function reactive<T extends object>(initial: T): T {
	const value = $state(initial);
	return value;
}
