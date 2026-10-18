// An item's optional date: `YYYY-MM-DD` text, or null for no date. The server
// checks the same rule (src/api/ops.py, `_item_date`).

const ISO_DATE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;

/** True for a real calendar day written `YYYY-MM-DD` (2026-02-30 is not one). */
export function isItemDate(value: unknown): value is string {
	if (typeof value !== 'string' || !ISO_DATE.test(value)) return false;
	const [year, month, day] = value.split('-').map(Number);
	if (year < 1) return false;
	// setUTCFullYear, not Date.UTC: Date.UTC maps years 0-99 to 1900-1999.
	const date = new Date(0);
	date.setUTCFullYear(year, month - 1, day);
	return (
		date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
	);
}
