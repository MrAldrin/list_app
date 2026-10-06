// The "Hide checked-off items" settings, as NiceGUI's `visibility_settings_ui`.
// Rules: docs/checked-item-visibility.md. Each control sends only what it changed.

import { MAX_HIDE_DONE_COUNT, type HideDone, type HideDoneMode } from '#lib/data/index.ts';

/** NiceGUI's warning for a bad number. */
export const COUNT_WARNING = `Enter a whole number between 1 and ${MAX_HIDE_DONE_COUNT}.`;

/** The modes the "Hide mode" choice offers, with NiceGUI's labels. */
export const HIDE_MODES: readonly { mode: Exclude<HideDoneMode, 'off'>; label: string }[] = [
	{ mode: 'all', label: 'All' },
	{ mode: 'age', label: 'After X days' },
	{ mode: 'recent', label: 'Keep last X' }
];

/** A count typed into a number field, or null unless a whole number from 1 to 100,000. */
export function parseHideDoneCount(text: string): number | null {
	if (!text.trim()) return null;
	const value = Number(text);
	return Number.isInteger(value) && value >= 1 && value <= MAX_HIDE_DONE_COUNT ? value : null;
}

export type HideDoneControl =
	| { field: 'enabled'; value: boolean }
	| { field: 'mode'; value: HideDoneMode }
	| { field: 'age_days'; value: number }
	| { field: 'recent_count'; value: number };

/**
 * What to send for one control change, or null when nothing changes.
 * Turning hiding on picks "All" (not the last mode); turning it off keeps the counts.
 */
export function hideDoneChange(
	current: HideDone,
	control: HideDoneControl
): Partial<HideDone> | null {
	switch (control.field) {
		case 'enabled':
			if (control.value === (current.mode !== 'off')) return null;
			return { mode: control.value ? 'all' : 'off' };
		case 'mode':
			if (control.value === 'off' || control.value === current.mode) return null;
			return { mode: control.value };
		case 'age_days':
		case 'recent_count':
			if (control.value === current[control.field]) return null;
			return { [control.field]: control.value };
	}
}
