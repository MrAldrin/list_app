"""The pure zone resolver (src/reminders/zoned_time.py), with tzdata only."""

import subprocess
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

from reminders.zoned_time import (
    TimeZoneUnavailable,
    format_utc,
    load_zone,
    reminder_instant,
    resolve_wall_time,
)

SRC = Path(__file__).resolve().parents[1] / "src"


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)


def test_oslo_spring_gap_resolves_to_first_valid_instant_after_gap():
    # 02:30 does not exist on 2026-03-29 in Oslo (clocks jump 02:00 -> 03:00).
    # The first valid instant is 03:00 CEST = 01:00 UTC, not 02:30 + gap width.
    instant = resolve_wall_time(
        date(2026, 3, 29), time(2, 30), load_zone("Europe/Oslo")
    )
    assert instant == utc(2026, 3, 29, 1, 0)


def test_oslo_fold_resolves_to_first_occurrence():
    # 02:30 happens twice on 2026-10-25; the first is still CEST (+02:00).
    instant = resolve_wall_time(
        date(2026, 10, 25), time(2, 30), load_zone("Europe/Oslo")
    )
    assert instant == utc(2026, 10, 25, 0, 30)


def test_ordinary_time_uses_its_offset():
    assert resolve_wall_time(
        date(2026, 11, 10), time(9, 0), load_zone("Europe/Oslo")
    ) == utc(2026, 11, 10, 8, 0)


@pytest.mark.parametrize(
    ("zone", "day", "clock", "expected"),
    [
        # Positive offset, southern-hemisphere DST (Sydney).
        ("Australia/Sydney", date(2026, 10, 5), time(2, 30), utc(2026, 10, 4, 15, 30)),
        # Negative offset without DST (Honolulu).
        ("Pacific/Honolulu", date(2026, 1, 1), time(0, 0), utc(2026, 1, 1, 10, 0)),
        # Leap day.
        ("Europe/Oslo", date(2028, 2, 29), time(12, 0), utc(2028, 2, 29, 11, 0)),
        # Year boundary, New Year in Auckland (+13 in January).
        ("Pacific/Auckland", date(2027, 1, 1), time(0, 0), utc(2026, 12, 31, 11, 0)),
    ],
)
def test_positive_and_negative_offsets_and_edges(zone, day, clock, expected):
    assert resolve_wall_time(day, clock, load_zone(zone)) == expected


def test_sydney_spring_gap_is_first_valid_instant():
    # Sydney 2026-10-04 02:00-03:00 is skipped (AEST +10 -> AEDT +11).
    instant = resolve_wall_time(
        date(2026, 10, 4), time(2, 30), load_zone("Australia/Sydney")
    )
    assert instant == utc(2026, 10, 3, 16, 0)


def test_minutes_and_hours_are_elapsed_time_from_the_anchor():
    zone = load_zone("Europe/Oslo")
    anchor = resolve_wall_time(date(2026, 3, 30), time(12, 0), zone)
    assert reminder_instant(
        date(2026, 3, 30), time(12, 0), zone, unit="hours", amount=2
    ) == anchor - timedelta(hours=2)
    assert reminder_instant(
        date(2026, 3, 30), time(12, 0), zone, unit="minutes", amount=90
    ) == anchor - timedelta(minutes=90)


def test_days_and_weeks_keep_the_local_clock_across_a_dst_change():
    # The anchor is 2026-03-30 09:00 CEST (07:00 UTC). One calendar day
    # earlier is 2026-03-29 09:00 CEST too, but the elapsed time is 23 hours.
    zone = load_zone("Europe/Oslo")
    one_day = reminder_instant(
        date(2026, 3, 30), time(9, 0), zone, unit="days", amount=1
    )
    assert one_day == utc(2026, 3, 29, 7, 0)
    one_week = reminder_instant(
        date(2026, 3, 30), time(9, 0), zone, unit="weeks", amount=1
    )
    assert one_week == utc(2026, 3, 23, 8, 0)


def test_reminder_day_in_the_gap_resolves_to_the_gap_end():
    # A date-only item reminder at 02:30 on the gap day resolves to 03:00.
    instant = reminder_instant(
        date(2026, 3, 30),
        time(2, 30),
        load_zone("Europe/Oslo"),
        unit="days",
        amount=1,
    )
    assert instant == utc(2026, 3, 29, 1, 0)


def test_negative_amounts_are_rejected():
    with pytest.raises(ValueError):
        reminder_instant(
            date(2026, 1, 1), time(9, 0), load_zone("UTC"), unit="days", amount=-1
        )


def test_reminder_before_the_calendar_is_a_value_error():
    with pytest.raises(ValueError):
        reminder_instant(
            date(1, 1, 1), time(9, 0), load_zone("UTC"), unit="weeks", amount=365
        )


@pytest.mark.parametrize("name", ["", "Europe", "Nope/Zone", "../etc/passwd", "/x"])
def test_unknown_or_unsafe_zone_names_are_refused(name):
    with pytest.raises(TimeZoneUnavailable):
        load_zone(name)


def test_format_utc_uses_milliseconds_and_z():
    assert format_utc(utc(2026, 3, 29, 1, 0)) == "2026-03-29T01:00:00.000Z"


def test_zone_resolution_works_with_system_zoneinfo_disabled():
    # PYTHONTZPATH='' turns off the system zone database; only the tzdata
    # package can answer. This proves the runtime dependency is real.
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "from reminders.zoned_time import load_zone, resolve_wall_time;"
        "from datetime import date, time;"
        "z = load_zone('Europe/Oslo');"
        "print(resolve_wall_time(date(2026, 3, 29), time(2, 30), z).isoformat())"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SRC)],
        capture_output=True,
        text=True,
        env={"PYTHONTZPATH": "", "PATH": "/usr/bin:/bin"},
        check=True,
    )
    assert result.stdout.strip() == "2026-03-29T01:00:00+00:00"
