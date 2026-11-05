export const DEFAULT_TIME_ZONE = 'Europe/Oslo';

export function validTime(value: string): boolean {
	return /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
}

/** Canonical spelling for a new wall intent, or null when the browser cannot use it. */
export function canonicalTimeZone(value: string): string | null {
	const zone = value.trim();
	// The shared item API limits zone names to 64 Unicode characters.
	if (!zone || [...zone].length > 64 || /^[+-]/.test(zone)) return null;
	try {
		const canonical = new Intl.DateTimeFormat('en', { timeZone: zone }).resolvedOptions().timeZone;
		return canonical && [...canonical].length <= 64 && !/^[+-]/.test(canonical) ? canonical : null;
	} catch {
		return null;
	}
}
