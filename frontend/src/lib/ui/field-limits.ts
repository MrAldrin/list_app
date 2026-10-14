// Length limits for user text; the server checks the same limits
// (src/field_limits.py). Browsers count some emoji as two, so the field may
// stop a little early, never late.
export const MAX_NAME_LENGTH = 100;
export const MAX_DESCRIPTION_LENGTH = 1000;
export const MAX_TAG_LENGTH = 30;
