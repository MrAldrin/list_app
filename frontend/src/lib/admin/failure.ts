// What the admin screens do with a failed answer: a warning toast with its
// message and, when admin sign-in is gone, the sign-in prompt.

import { admin } from '#lib/data/index.ts';
import type { Failure } from '#lib/data/result.ts';
import { toasts } from '#lib/ui/toasts.svelte.ts';

/**
 * Shows a failed admin answer as a warning toast. When admin sign-in was lost
 * (`admin.isSignedOut`), `clear` drops the page's open parts first, then
 * `onSignedOut` shows the sign-in prompt.
 */
export function showAdminFailure(
	failure: Failure,
	onSignedOut: () => void,
	clear?: () => void
): void {
	toasts.show(failure.message, 'warning');
	if (!admin.isSignedOut(failure)) return;
	clear?.();
	onSignedOut();
}
