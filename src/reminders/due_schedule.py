"""An item's shared due schedule: date, optional due time and time zone.

Stored on the item as `date`, `due_time`, `due_timezone`, the derived `due_at`
(UTC) and `due_cycle` (see migration 15 and docs/api-lists-items.md).

- A date-only item has no time and no zone. Its `due_at` is NULL.
- A timed item has a date, a time and a zone, all together. `due_at` is the
  zone's first valid instant for that wall time (zoned_time.resolve_wall_time).
- `due_cycle` is a new server-generated UUID whenever the date, time or zone
  changes, and whenever a checked item is unchecked. Name, description,
  quantity, tag and retry changes keep it. A deleted item's undo is a new
  item and gets a new cycle, so an old cycle is never reused.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date as calendar_date
from datetime import time as clock_time

from reminders.zoned_time import format_utc, load_zone, resolve_wall_time

# A 24-hour clock time as HH:MM, from 00:00 to 23:59.
CLOCK_TIME = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")


@dataclass(frozen=True)
class DueSchedule:
    """Date (YYYY-MM-DD), time (HH:MM) and zone, each None when absent.

    Structure only: a stored or merged schedule is checked by
    `checked_due_schedule`; `due_at` resolves it and may raise ValueError.
    """

    date: str | None = None
    time: str | None = None
    timezone: str | None = None

    def due_at(self) -> str | None:
        """The UTC instant as stored, or None for a date-only item.

        ValueError when the zone is unknown or its data is missing, or when the
        instant is outside the supported calendar.
        """
        if self.time is None or self.timezone is None or self.date is None:
            return None
        zone = load_zone(self.timezone)
        try:
            instant = resolve_wall_time(
                calendar_date.fromisoformat(self.date),
                clock_time.fromisoformat(self.time),
                zone,
            )
        except OverflowError as error:
            raise ValueError(
                "The due date is outside the supported calendar"
            ) from error
        return format_utc(instant)


def new_due_cycle() -> str:
    """A new cycle identity: a random UUID v4 as lowercase text."""
    return str(uuid.uuid4())


def checked_due_schedule(
    date: str | None, time: str | None, timezone: str | None
) -> DueSchedule:
    """The schedule if its parts go together, else ValueError.

    A time needs a date and a zone; a zone needs a time; a date alone is fine.
    The date must already be a checked YYYY-MM-DD. The zone's name is not
    looked up here (see `DueSchedule.due_at`).
    """
    if date is None:
        if time is not None or timezone is not None:
            raise ValueError("A due time and time zone need a date")
        return DueSchedule()
    if time is None:
        if timezone is not None:
            raise ValueError("A time zone needs a due time")
        return DueSchedule(date=date)
    if timezone is None:
        raise ValueError("A due time needs a time zone")
    if not CLOCK_TIME.fullmatch(time):
        raise ValueError("time must be HH:MM")
    return DueSchedule(date=date, time=time, timezone=timezone)


def merge_due_edit(
    stored: DueSchedule,
    *,
    date_given: bool,
    date: str | None,
    time_given: bool,
    time: str | None,
    zone_given: bool,
    zone: str | None,
) -> DueSchedule:
    """The schedule an edit wants. A part not given keeps the stored value.

    Clearing the date clears the time and zone. Clearing the time clears the
    zone. A time or zone sent without a date, or a zone without a time, is a
    ValueError, as is a time without a zone.
    """
    if not (date_given or time_given or zone_given):
        return stored
    new_date = date if date_given else stored.date
    if new_date is None:
        if (time_given and time is not None) or (zone_given and zone is not None):
            raise ValueError("A due time and time zone need a date")
        return DueSchedule()
    new_time = time if time_given else stored.time
    if new_time is None:
        if zone_given and zone is not None:
            raise ValueError("A time zone needs a due time")
        return DueSchedule(date=new_date)
    new_zone = zone if zone_given else stored.timezone
    return checked_due_schedule(new_date, new_time, new_zone)
