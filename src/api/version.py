"""The API version the frontend must match (see docs/api.md, "API version").

Raise it by hand when a change would break a frontend that is still open in a
browser: a changed meaning, a removed field or a new rule for writes. Adding
a field or an endpoint does not need a new version. The frontend keeps the
same number in `frontend/src/lib/data/compat.svelte.ts`; a test checks both.
"""

API_VERSION = 1
API_VERSION_HEADER = "X-Api-Version"
