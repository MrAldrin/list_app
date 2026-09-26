"""Pure visibility rules for checked-off list items."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

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
        if type(value) is not int or not 0 <= value <= MAX_HIDE_DONE_COUNT:
            raise ValueError(
                f"{name} must be a whole number between 0 and {MAX_HIDE_DONE_COUNT}"
            )


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_completion_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc_datetime(parsed)


def filter_visible_items(
    items: Sequence[dict[str, Any]],
    mode: str = DEFAULT_HIDE_DONE_MODE,
    age_days: int = DEFAULT_HIDE_DONE_AGE_DAYS,
    recent_count: int = DEFAULT_HIDE_DONE_RECENT_COUNT,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return visible rows without changing them or the original list.

    Call this on the complete list before applying tag filters so ``recent`` is
    counted across the entire list. Items with unknown completion times remain
    visible in age mode and rank behind known times in recent mode.
    """
    validate_visibility_settings(mode, age_days, recent_count)
    if mode == "off":
        return list(items)

    if mode == "all" or (mode == "age" and age_days == 0):
        return [item for item in items if not item.get("done", False)]

    if mode == "age":
        current_time = _utc_datetime(now if now is not None else datetime.now(UTC))
        cutoff = current_time - timedelta(days=age_days)
        visible = []
        for item in items:
            if not item.get("done", False):
                visible.append(item)
                continue
            completed_at = _parse_completion_time(item.get("completed_at"))
            if completed_at is None or completed_at > cutoff:
                visible.append(item)
        return visible

    checked_items = [item for item in items if item.get("done", False)]

    def recent_key(item: Mapping[str, Any]) -> tuple[bool, datetime, int]:
        completed_at = _parse_completion_time(item.get("completed_at"))
        return (
            completed_at is not None,
            completed_at or datetime.min.replace(tzinfo=UTC),
            item.get("id", 0),
        )

    retained = {
        id(item)
        for item in sorted(checked_items, key=recent_key, reverse=True)[:recent_count]
    }
    return [
        item for item in items if not item.get("done", False) or id(item) in retained
    ]
