// Does this page still match the server? The server sends its API version on
// every API answer (docs/api.md, "API version"). A different number means a
// deploy replaced the server while this page was open. Then writes stop and
// the page offers a reload. Nothing reloads by itself.

/**
 * The API version this build was made for. The server keeps the same number in
 * `src/api/version.py`; a Python test checks that both match.
 */
export const EXPECTED_API_VERSION = 1;

export const API_VERSION_HEADER = 'X-Api-Version';

export const INCOMPATIBLE_CODE = 'incompatible_version';
export const INCOMPATIBLE_MESSAGE = 'A new version is available. Reload to keep making changes.';

class Compat {
	/** True from the first answer with another version until the page reloads. */
	incompatible = $state(false);
}

export const compat = new Compat();

/**
 * Looks at the headers of one API answer. An answer without the header, or with
 * one that is not a whole number, is not a sign of a new version: proxy and
 * maintenance pages look like that during a deploy, and blocking writes for
 * them would punish the user for a short outage. Only a clear other number counts.
 */
export function checkApiVersion(headers: Pick<Headers, 'get'>): void {
	const sent = headers.get(API_VERSION_HEADER)?.trim();
	if (!sent || !/^\d+$/.test(sent)) return;
	if (Number(sent) !== EXPECTED_API_VERSION) compat.incompatible = true;
}

/** For tests only: a page cannot become compatible again without a reload. */
export function resetCompat(): void {
	compat.incompatible = false;
}
