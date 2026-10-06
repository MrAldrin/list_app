// Sharing a room or list link, as NiceGUI's `share_button` does
// (`src/ui/sharing.py`): the phone's share sheet when there is one, else a
// dialog with the link and "Copy link".

export type ShareKind = 'room' | 'list';

/** The access reminder shown inside the app, never sent with the URL. */
export function shareMessage(kind: ShareKind): string {
	return kind === 'room'
		? 'The recipient will also need the room password.'
		: 'Anyone with this link can open this list.';
}

/**
 * The full address of an app path, for sending to another device. Built from
 * the path alone, never from the current address, which may hold other
 * parameters.
 */
export function absoluteUrl(path: string, origin: string = window.location.origin): string {
	return new URL(path, origin).href;
}

export type ShareOutcome = 'shared' | 'cancelled' | 'fallback';

type ShareNavigator = Partial<Pick<Navigator, 'share'>>;

/**
 * Opens the share sheet. `fallback` means: show the dialog instead (no share
 * sheet, or it failed). Call it straight from a click, before any other
 * `await`: browsers allow the share sheet only right after a tap.
 */
export async function shareNatively(
	url: string,
	nav: ShareNavigator = navigator
): Promise<ShareOutcome> {
	if (typeof nav.share !== 'function') return 'fallback';
	try {
		// Extra text or a title can become part of iPhone’s copied link.
		await nav.share({ url });
		return 'shared';
	} catch (error) {
		// The user closed the sheet: that is a choice, not a failure.
		if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled';
		return 'fallback';
	}
}

type CopyClipboard = Partial<Pick<Clipboard, 'writeText'>>;

/**
 * Copies text. The clipboard API needs HTTPS; on plain HTTP (local network
 * tests) the selected text in `field` is copied the old way.
 */
export async function copyText(
	text: string,
	field?: HTMLInputElement,
	clipboard: CopyClipboard | undefined = navigator.clipboard
): Promise<boolean> {
	if (clipboard?.writeText) {
		try {
			await clipboard.writeText(text);
			return true;
		} catch {
			// Not allowed here; try the old way.
		}
	}
	if (!field) return false;
	field.select();
	try {
		// Deprecated, but the only way without the clipboard API.
		return document.execCommand('copy');
	} catch {
		return false;
	}
}
