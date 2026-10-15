"""Pure visibility rules for checked-off list items."""

from datetime import UTC, datetime

DEFAULT_HIDE_DONE_MODE = "off"
DEFAULT_HIDE_DONE_AGE_DAYS = 7
DEFAULT_HIDE_DONE_RECENT_COUNT = 10
MAX_HIDE_DONE_COUNT = 100_000
HIDE_DONE_MODES = frozenset({"off", "all", "age", "recent"})


def validate_visibility_settings(mode: str, age_days: int, recent_count: int) -> None:
    """Reject unknown modes and counts outside the supported whole-number range."""
    if not isinstance(mode, str) or mode not in HIDE_DONE_MODES:
        raise ValueError(f"Unknown checked-item visibility mode: {mode!r}")
    for name, value in (
        ("age_days", age_days),
        ("recent_count", recent_count),
    ):
        if type(value) is not int or not 1 <= value <= MAX_HIDE_DONE_COUNT:
            raise ValueError(
                f"{name} must be a whole number between 1 and {MAX_HIDE_DONE_COUNT}"
            )


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_completion_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc_datetime(parsed)
