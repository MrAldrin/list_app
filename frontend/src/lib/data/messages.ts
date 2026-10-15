// User-facing text for sign-in, sign-out and saved-data failures.

export const SIGNIN_LOCK_UNAVAILABLE =
	'Room sign-in is waiting for a pending sign-out to finish. Reopen this page in a supported secure browser and try again.';
export const SIGNIN_STATE_UNAVAILABLE =
	'Room sign-in is blocked because pending sign-out state could not be read. Allow local storage, then retry.';
export const SIGNIN_REFRESH_FAILED =
	'Room access could not be confirmed. The app will retry before enabling changes.';
export const SNAPSHOT_UNAVAILABLE = 'Saved data could not be updated on this device.';
export const LOGOUT_SERVER_PENDING =
	'This sign-out cleared the visible room and its prior saved copy, but server sign-out is pending. A newer sign-in may have restored access; the room cookie may still work. Retry in a secure browser with Web Locks.';
export const LOGOUT_LOCAL_CLEAR_UNCONFIRMED =
	'Room data was cleared from this page, but saved data could not be confirmed cleared on this device. Server sign-out was not attempted; the room cookie may still work.';
export const LOGOUT_MARKER_UNACKNOWLEDGED =
	'Server sign-out succeeded and its cookie was cleared, but the local sign-out marker could not be acknowledged. Room access stays blocked until the marker can be resolved.';
export const PENDING_OPERATION_NOTICE =
	'A change may still be saving. Sign in again to check its status before retrying it.';
