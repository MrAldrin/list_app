/** The shared item API accepts zone names at most 64 characters long. */
export function usableTimeZone(value: string): boolean {
	const zone = value.trim();
	if (!zone || [...zone].length > 64) return false;
	try {
		new Intl.DateTimeFormat('en', { timeZone: zone });
		// Intl also accepts bare numeric offsets, which are not IANA zone names.
		return !/^[+-]/.test(zone);
	} catch {
		return false;
	}
}
