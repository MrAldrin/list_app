"""Personal reminder rules: strict input, normalization and fixed-rule identity.

Pure checks with a fixed clock and fixed rule ids. Oslo's 2026-03-29 gap and
2026-10-25 repeat come from the shared zone resolver in `zoned_time`.
"""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from reminders import rules
from reminders.rules import FixedRule, RelativeRule, normalize_rules

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
RULE_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "22222222-2222-4222-8222-222222222222"
NEW_ID = "33333333-3333-4333-8333-333333333333"


def fixed_id() -> str:
    return NEW_ID


def relative(amount: object, unit: object) -> dict:
    return {"kind": "relative", "amount": amount, "unit": unit}


def fixed(date: str, time: str, zone: str = "Europe/Oslo", **extra: object) -> dict:
    return {"kind": "fixed", "date": date, "time": time, "timezone": zone, **extra}


def stored(
    rule_id: str = RULE_ID,
    *,
    date: str = "2026-06-01",
    time: str = "09:00",
    zone: str = "Europe/Oslo",
    instant: datetime = datetime(2026, 6, 1, 7, 0, tzinfo=UTC),
    activation: datetime = datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
) -> FixedRule:
    return FixedRule(rule_id, date, time, zone, instant, activation)


def normalize(inputs: list, **kwargs: object) -> tuple:
    return normalize_rules(inputs, now=NOW, make_rule_id=fixed_id, **kwargs)


def test_relative_units_normalize_to_elapsed_or_calendar_rules():
    result = normalize([relative(60, "minutes"), relative(2, "hours")])
    assert result == (RelativeRule("elapsed", 60), RelativeRule("elapsed", 120))
    assert normalize([relative(2, "weeks")]) == (RelativeRule("calendar", 14),)


def test_equivalent_units_are_duplicates():
    with pytest.raises(ValueError, match="Duplicate relative"):
        normalize([relative(60, "minutes"), relative(1, "hours")])
    with pytest.raises(ValueError, match="Duplicate relative"):
        normalize([relative(7, "days"), relative(1, "weeks")])


def test_calendar_day_is_not_24_elapsed_hours():
    days = normalize([relative(1, "days")])[0]
    hours = normalize([relative(24, "hours")])[0]
    assert days.key == "calendar:1d"
    assert hours.key == "elapsed:1440m"
    assert days != hours


def test_zero_in_any_unit_is_one_at_due_rule():
    assert normalize([relative(0, "weeks")]) == (RelativeRule("at_due", 0),)
    with pytest.raises(ValueError, match="Duplicate relative"):
        normalize([relative(0, "minutes"), relative(0, "days")])


@pytest.mark.parametrize(
    ("amount", "unit"),
    [
        (True, "days"),
        (1.0, "days"),
        ("1", "days"),
        (-1, "days"),
        (1, "months"),
        (366, "days"),
        (53, "weeks"),
        (8761, "hours"),
        (525601, "minutes"),
    ],
)
def test_invalid_relative_inputs_are_rejected(amount: object, unit: object):
    with pytest.raises(ValueError):
        normalize([relative(amount, unit)])


def test_unknown_or_missing_fields_are_rejected():
    with pytest.raises(ValueError):
        normalize([{"kind": "relative", "amount": 1, "unit": "days", "x": 1}])
    with pytest.raises(ValueError):
        normalize([{"kind": "relative", "amount": 1}])
    with pytest.raises(ValueError):
        normalize([fixed("2026-06-01", "09:00", id=RULE_ID, instant="x")])
    with pytest.raises(ValueError):
        normalize([{"kind": "other"}])


def test_at_most_five_rules_and_empty_is_allowed():
    assert normalize([]) == ()
    six = [relative(n, "days") for n in range(1, 7)]
    with pytest.raises(ValueError, match="At most 5"):
        normalize(six)


def test_inputs_and_existing_rules_are_not_mutated():
    inputs = [relative(1, "days"), fixed("2026-06-01", "09:00")]
    existing = [stored()]
    before = (repr(inputs), repr(existing))
    normalize_rules(inputs, existing_rules=existing, now=NOW, make_rule_id=fixed_id)
    assert (repr(inputs), repr(existing)) == before


def test_fixed_gap_and_fold_use_the_shared_resolver():
    gap = normalize([fixed("2026-03-29", "02:30")])[0]
    fold = normalize([fixed("2026-10-25", "02:30")])[0]
    assert gap.instant == datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    assert fold.instant == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)


def test_new_fixed_rule_gets_injected_id_and_activation():
    rule = normalize([fixed("2026-06-01", "09:00")])[0]
    assert rule == FixedRule(
        NEW_ID,
        "2026-06-01",
        "09:00",
        "Europe/Oslo",
        datetime(2026, 6, 1, 7, 0, tzinfo=UTC),
        NOW,
    )


def test_default_identity_is_a_lowercase_uuid():
    identity = rules.new_rule_id()
    assert identity == str(uuid.UUID(identity))


@pytest.mark.parametrize(
    ("date", "time", "zone", "message"),
    [
        ("2026-02-30", "09:00", "Europe/Oslo", None),
        ("2026-6-1", "09:00", "Europe/Oslo", "date must"),
        ("2026-06-01", "9:00", "Europe/Oslo", "time must"),
        ("2026-06-01", "24:00", "Europe/Oslo", "time must"),
        ("2026-06-01", "09:00", "Mars/Olympus", "Unknown time zone"),
        ("2026-01-01", "11:00", "Europe/Oslo", "must be in the future"),
    ],
)
def test_invalid_or_past_fixed_wall_time_is_rejected(
    date: str, time: str, zone: str, message: str | None
):
    with pytest.raises(ValueError, match=message):
        normalize([fixed(date, time, zone)])


def test_unchanged_existing_rule_keeps_identity_after_time_passes():
    existing = [stored()]
    result = normalize_rules(
        [fixed("2026-06-01", "09:00", id=RULE_ID)],
        existing_rules=existing,
        now=datetime(2027, 1, 1, tzinfo=UTC),
        make_rule_id=fixed_id,
    )
    assert result == (existing[0],)


def test_unchanged_existing_rule_without_id_keeps_identity(monkeypatch):
    existing = [stored()]

    def resolver_must_not_run(*args: object) -> None:
        raise AssertionError("resolved an unchanged fixed rule")

    monkeypatch.setattr(rules, "resolve_wall_time", resolver_must_not_run)
    result = normalize_rules(
        [fixed("2026-06-01", "09:00")],
        existing_rules=existing,
        now=datetime(2027, 1, 1, tzinfo=UTC),
        make_rule_id=fixed_id,
    )
    assert result == (existing[0],)


def test_changed_fixed_rule_gets_new_id_and_future_activation():
    existing = [stored()]
    result = normalize_rules(
        [fixed("2026-06-02", "09:00", id=RULE_ID)],
        existing_rules=existing,
        now=NOW,
        make_rule_id=fixed_id,
    )[0]
    assert result.id == NEW_ID
    assert result.instant == datetime(2026, 6, 2, 7, 0, tzinfo=UTC)
    assert result.activation == NOW


def test_changed_fixed_rule_in_the_past_is_rejected():
    with pytest.raises(ValueError, match="must be in the future"):
        normalize_rules(
            [fixed("2025-12-31", "09:00", id=RULE_ID)],
            existing_rules=[stored(date="2026-06-01")],
            now=NOW,
            make_rule_id=fixed_id,
        )


def test_forged_or_foreign_id_is_rejected():
    with pytest.raises(ValueError, match="Unknown fixed reminder id"):
        normalize(
            [fixed("2026-06-01", "09:00", id=OTHER_ID)],
            existing_rules=[stored()],
        )
    with pytest.raises(ValueError, match="id must be a UUID"):
        normalize([fixed("2026-06-01", "09:00", id="not-a-uuid")])
    with pytest.raises(ValueError, match="lowercase"):
        normalize(
            [fixed("2026-06-01", "09:00", id="AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA")],
            existing_rules=[stored()],
        )


def test_one_stored_rule_cannot_be_claimed_twice():
    with pytest.raises(ValueError, match="used once"):
        normalize(
            [
                fixed("2026-06-01", "09:00", id=RULE_ID),
                fixed("2026-06-01", "09:00", id=RULE_ID),
            ],
            existing_rules=[stored()],
        )


def test_two_fixed_labels_for_one_utc_instant_are_duplicates():
    with pytest.raises(ValueError, match="same time"):
        normalize(
            [
                fixed("2026-06-01", "09:00", "Europe/Oslo"),
                fixed("2026-06-01", "07:00", "UTC"),
            ]
        )


def test_naive_now_is_rejected():
    with pytest.raises(ValueError, match="aware"):
        normalize_rules([], now=datetime(2026, 1, 1))


def test_now_is_converted_to_utc_for_activation():
    plus_two = timezone(timedelta(hours=2))
    result = normalize_rules(
        [fixed("2026-06-01", "09:00")],
        now=datetime(2026, 1, 1, 14, tzinfo=plus_two),
        make_rule_id=fixed_id,
    )[0]
    assert result.activation == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert result.activation.tzinfo == UTC
