"""Admin sign-in rules, shared by NiceGUI's /admin and the JSON API.

The admin password is `APP_PASSWORD`. Being signed in as admin is a flag in
NiceGUI's per-browser user storage (`app.storage.user`, found through
NiceGUI's signed session cookie), so signing in on one UI signs in the other.
Admin sign-in never grants room access.
"""

import hmac

from config import require_app_password

# The key NiceGUI's admin pages read in `app.storage.user`.
ADMIN_STORAGE_KEY = "authenticated"


def admin_password_matches(candidate: str) -> bool:
    """Compare with APP_PASSWORD in constant time (same result as `==`)."""
    expected = require_app_password()
    # `surrogatepass` keeps any Python string comparable, as `==` would.
    return hmac.compare_digest(
        candidate.encode("utf-8", "surrogatepass"),
        expected.encode("utf-8", "surrogatepass"),
    )
