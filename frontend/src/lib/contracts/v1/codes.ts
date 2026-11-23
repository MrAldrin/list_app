// Kept separate so browser error handling does not load Effect at runtime.
export const API_ERROR_CODES = [
	'invalid_request',
	'invalid_password',
	'too_many_attempts',
	'not_authenticated',
	'admin_required',
	'share_unavailable',
	'list_unavailable',
	'wrong_password',
	'forbidden_origin',
	'not_found',
	'room_unavailable',
	'invitation_unavailable',
	'op_id_reused',
	'revision_conflict',
	'not_enrolled',
	'internal_error',
	'unavailable'
] as const;

export const REJECTION_CODES = [
	'invalid_name',
	'duplicate_name',
	'duplicate_active',
	'undo_name_taken',
	'changed_meanwhile',
	'list_unavailable',
	'item_not_found',
	'unknown_tag',
	'too_long',
	'too_many',
	'invalid_due',
	'time_zone_unavailable'
] as const;
