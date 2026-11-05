"""Wall-clock times in an IANA zone, resolved to UTC instants.

The one resolver for due and reminder times. Later previews and the scheduler
must call it rather than adding their own DST rules.

- A wall time that does not exist (a spring-forward gap) resolves to the first
  valid instant after the gap: Oslo 2026-03-29 02:30 is 03:00 CEST.
- A wall time that occurs twice (fall-back overlap) resolves to its first
  occurrence (`fold=0`).
- Minutes and hours are elapsed time from the resolved instant. Days and weeks
  are calendar days: the same local clock time on an earlier local date.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimeZoneUnavailable(ValueError):
    """The name is not a known IANA zone, or its zone data is not installed."""


def load_zone(name: str) -> ZoneInfo:
    """The zone called `name`. Never falls back to UTC or another zone."""
    try:
        return ZoneInfo(name)
    except (ValueError, OSError, ZoneInfoNotFoundError) as error:
        raise TimeZoneUnavailable(f"Unknown time zone: {name!r}") from error


def _utc_offset(wall: datetime, zone: ZoneInfo, fold: int) -> timedelta:
    offset = wall.replace(tzinfo=zone, fold=fold).utcoffset()
    if offset is None:
        raise ValueError("Zone gave no UTC offset")
    return offset


def _first_second_with_offset(
    low: datetime, high: datetime, offset: timedelta, zone: ZoneInfo
) -> datetime:
    """The first whole second in [low, high] whose UTC offset is `offset`.

    Requires that `low` has another offset and `high` has `offset`, so exactly
    one transition lies between them. Binary search over whole seconds.
    """
    first = int(low.timestamp())
    last = int(high.timestamp())
    while first < last:
        middle = (first + last) // 2
        if datetime.fromtimestamp(middle, zone).utcoffset() == offset:
            last = middle
        else:
            first = middle + 1
    return datetime.fromtimestamp(first, UTC)


def resolve_wall_time(day: date, clock: time, zone: ZoneInfo) -> datetime:
    """The UTC instant at which `zone` first shows `day` at `clock`."""
    wall = datetime.combine(day, clock)
    earlier_offset = _utc_offset(wall, zone, fold=0)
    instant = (wall - earlier_offset).replace(tzinfo=UTC)
    shown = instant.astimezone(zone).replace(tzinfo=None)
    if shown == wall:
        # Not in a gap. With fold=0 this is the first occurrence of a repeat.
        return instant
    # In a gap: `fold=0` used the offset from before the transition. The
    # transition lies between the two candidate instants.
    later_offset = _utc_offset(wall, zone, fold=1)
    low = (wall - later_offset).replace(tzinfo=UTC)
    high = (wall - earlier_offset).replace(tzinfo=UTC)
    return _first_second_with_offset(low, high, later_offset, zone)


def reminder_instant(
    day: date,
    clock: time,
    zone: ZoneInfo,
    *,
    unit: Literal["minutes", "hours", "days", "weeks"],
    amount: int,
) -> datetime:
    """`amount` units before the anchor `day` at `clock` in `zone`, as UTC.

    Minutes and hours subtract elapsed time from the resolved anchor. Days and
    weeks subtract calendar days, then resolve the same clock time again.
    """
    if amount < 0:
        raise ValueError("amount must not be negative")
    try:
        if unit in ("minutes", "hours"):
            elapsed = timedelta(minutes=amount if unit == "minutes" else amount * 60)
            return resolve_wall_time(day, clock, zone) - elapsed
        calendar_days = amount if unit == "days" else amount * 7
        return resolve_wall_time(day - timedelta(days=calendar_days), clock, zone)
    except OverflowError as error:
        raise ValueError("The reminder is before the calendar starts") from error


def format_utc(instant: datetime) -> str:
    """A UTC instant as stored and published: milliseconds and Z, like created_at."""
    return (
        instant.astimezone(UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
