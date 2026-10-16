// Length limits for user text; the server checks the same limits
// (src/field_limits.py). Browsers count some emoji as two, so the field may
// stop a little early, never late.
export const MAX_NAME_LENGTH = 100;
export const MAX_DESCRIPTION_LENGTH = 1000;
export const MAX_TAG_LENGTH = 30;

// The room password minimum, for newly set passwords (src/field_limits.py).
// Sign-in does not check it. The server stays the rule; forms check it first
// only as a convenience.
export const MIN_PASSWORD_LENGTH = 4;

/**
 * The message for a new room password that is too short, or null. Blank
 * passwords are left to the server, which answers "Password cannot be empty".
 */
export function shortPasswordMessage(password: string): string | null {
	if (password.trim() === '') return null;
	if ([...password].length >= MIN_PASSWORD_LENGTH) return null;
	return `Password must be at least ${MIN_PASSWORD_LENGTH} characters`;
}
