import { building } from '$app/env';

export async function init(): Promise<void> {
	if (building || import.meta.env.MODE !== 'typescript-server') return;

	const { checkDatabase, runtime } = await import('#lib/server/runtime.ts');
	await runtime.runPromise(checkDatabase);
	process.once('sveltekit:shutdown', () => void runtime.dispose());
}
