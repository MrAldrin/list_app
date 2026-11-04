"""Personal reminder rules: strict input, normalization and fixed-rule identity.

Pure: no database, no real clock and no authentication. A later private policy
API calls `normalize_rules` with the rule list the client sent and the existing
fixed rules of one policy that the caller has already authorized.

Client input is a list of at most five dicts, each with exactly these keys:

- `{"kind": "relative", "amount": int, "unit": ...}` with unit `minutes`,
  `hours`, `days` or `weeks`. `amount` is a non-negative int (never a bool).
  Limits: minutes <= 525600, hours <= 8760, days <= 365, weeks <= 52.
- `{"kind": "fixed", "date": "YYYY-MM-DD", "time": "HH:MM",
  "timezone": IANA name}` with an optional `"id"`: the UUID of one existing
  fixed rule of the same policy.

Clients never send a canonical instant, an activation time, a key or a new id.

Relative rules normalize to `RelativeRule`:
- Minutes and hours are elapsed time: 60 minutes is 1 hour, one `elapsed` rule.
- Days and weeks are calendar days: 7 days is 1 week, one `calendar` rule.
  A calendar day is not 24 elapsed hours.
- Zero in any unit is the single `at_due` rule.
- Two inputs with the same normalized key are duplicates and are rejected.
  Rules of different kinds may resolve to the same instant; both are kept.

Fixed rules normalize to `FixedRule`. The wall time is resolved once with
`zoned_time.resolve_wall_time` (a gap moves to the first valid instant after it,
a repeat uses its first occurrence):
- Unchanged rules keep their stored `id`, `instant` and `activation`, even when
  the instant has passed or the zone data has changed. A rule is unchanged when
  it is matched by `id`, or without an `id` by its wall intent (date, time and
  zone equal to a stored rule that no other input has claimed), and its wall
  intent is the same.
- A new rule, or one whose wall intent changed, must resolve to a future
  instant. It gets a new `id` from `new_rule_id` and `activation` set to `now`.
- Two fixed rules resolving to the same UTC instant are duplicates, whatever
  their zone or wall labels.
- Fixed identity does not depend on the item's due cycle, so this module takes
  no due-cycle input.
"""

import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from datetime import date as calendar_date
from datetime import time as clock_time
from typing import Any, Literal

from reminders.due_schedule import CLOCK_TIME
from reminders.zoned_time import load_zone, resolve_wall_time

MAX_RULES = 5
MAX_ZONE_NAME_LENGTH = 64

# Largest relative offset per unit, equal to 365 days (weeks: 52 weeks is 364 days).
RELATIVE_LIMITS = {"minutes": 525_600, "hours": 8_760, "days": 365, "weeks": 52}

DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

RELATIVE_FIELDS = frozenset({"kind", "amount", "unit"})
FIXED_REQUIRED_FIELDS = frozenset({"kind", "date", "time", "timezone"})
FIXED_FIELDS = FIXED_REQUIRED_FIELDS | {"id"}


@dataclass(frozen=True)
class RelativeRule:
    """An offset before the anchor. `amount` is minutes or days, or 0 for at_due.

    Keys: `at-due`, `elapsed:<minutes>m` and `calendar:<days>d`.
    """

    basis: Literal["at_due", "elapsed", "calendar"]
    amount: int

    @property
    def key(self) -> str:
        if self.basis == "at_due":
            return "at-due"
        if self.basis == "elapsed":
            return f"elapsed:{self.amount}m"
        return f"calendar:{self.amount}d"


@dataclass(frozen=True)
class FixedRule:
    """A personal fixed reminder: wall intent, its resolved UTC instant and identity.

    `id` is the stable identity. `instant` and `activation` are UTC. The caller
    stores all five fields; clients never send the last three.
    """

    id: str
    date: str
    time: str
    timezone: str
    instant: datetime
    activation: datetime


Rule = RelativeRule | FixedRule


def new_rule_id() -> str:
    """A new fixed-rule identity: a random UUID v4 as lowercase text."""
    return str(uuid.uuid4())


def normalize_rules(
    inputs: Sequence[Mapping[str, Any]],
    *,
    existing_rules: Sequence[FixedRule] = (),
    now: datetime,
    make_rule_id: Callable[[], str] = new_rule_id,
) -> tuple[Rule, ...]:
    """The normalized rules for `inputs`, in input order.

    `existing_rules` are the trusted fixed rules of one already-authorized policy.
    `now` must be an aware datetime; it is converted to UTC.

    Raises ValueError for a malformed input, more than five rules, duplicate
    rules, an unknown or reused `id`, an unknown or unavailable zone, an
    impossible date or time, a new or changed fixed time that is not in the
    future, or two fixed rules at the same instant.
    """
    if not isinstance(inputs, list | tuple):
        raise ValueError("rules must be a list")
    if len(inputs) > MAX_RULES:
        raise ValueError(f"At most {MAX_RULES} reminder rules")
    now_utc = _aware_now(now)
    existing_by_id = _index_existing(existing_rules)
    reserved = _reserve_explicit_ids(inputs, existing_by_id)
    claimed: set[str] = set()
    rules: list[Rule] = []
    for raw in inputs:
        if not isinstance(raw, Mapping):
            raise ValueError("Each reminder rule must be an object")
        if raw.get("kind") == "relative":
            if set(raw) != RELATIVE_FIELDS:
                raise ValueError("A relative rule takes kind, amount and unit only")
            rules.append(_relative_rule(raw))
        elif raw.get("kind") == "fixed":
            keys = set(raw)
            if not FIXED_REQUIRED_FIELDS <= keys <= FIXED_FIELDS:
                raise ValueError("A fixed rule takes kind, date, time, timezone and id")
            rules.append(
                _fixed_rule(
                    raw, existing_by_id, reserved, claimed, now_utc, make_rule_id
                )
            )
        else:
            raise ValueError("kind must be relative or fixed")
    _reject_duplicates(rules)
    return tuple(rules)


def _aware_now(now: object) -> datetime:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("now must be an aware datetime")
    return now.astimezone(UTC)


def _index_existing(existing_rules: Sequence[FixedRule]) -> dict[str, FixedRule]:
    by_id: dict[str, FixedRule] = {}
    for rule in existing_rules:
        if not isinstance(rule, FixedRule):
            raise ValueError("existing_rules must be stored fixed rules")
        if rule.id in by_id:
            raise ValueError("Duplicate stored fixed rule id")
        by_id[rule.id] = rule
    return by_id


def _relative_rule(raw: Mapping[str, Any]) -> RelativeRule:
    amount = raw["amount"]
    unit = raw["unit"]
    if type(amount) is not int:
        raise ValueError("amount must be an integer")
    if amount < 0:
        raise ValueError("amount must not be negative")
    if type(unit) is not str or unit not in RELATIVE_LIMITS:
        raise ValueError("unit must be minutes, hours, days or weeks")
    if amount > RELATIVE_LIMITS[unit]:
        raise ValueError(f"{unit} must be at most {RELATIVE_LIMITS[unit]}")
    if amount == 0:
        return RelativeRule("at_due", 0)
    if unit == "minutes":
        return RelativeRule("elapsed", amount)
    if unit == "hours":
        return RelativeRule("elapsed", amount * 60)
    if unit == "days":
        return RelativeRule("calendar", amount)
    return RelativeRule("calendar", amount * 7)


def _reserve_explicit_ids(
    inputs: Sequence[Mapping[str, Any]], existing_by_id: Mapping[str, FixedRule]
) -> frozenset[str]:
    """Checks every explicit fixed `id` before any id-less input is matched.

    Each must be a canonical id of a stored rule, named by one input only.
    """
    reserved: set[str] = set()
    for raw in inputs:
        if (
            not isinstance(raw, Mapping)
            or raw.get("kind") != "fixed"
            or "id" not in raw
        ):
            continue
        given_id = _given_id(raw["id"])
        if given_id not in existing_by_id:
            raise ValueError("Unknown fixed reminder id")
        if given_id in reserved:
            raise ValueError("A fixed reminder id may be used once")
        reserved.add(given_id)
    return frozenset(reserved)


def _fixed_rule(
    raw: Mapping[str, Any],
    existing_by_id: Mapping[str, FixedRule],
    reserved: frozenset[str],
    claimed: set[str],
    now: datetime,
    new_rule_id: Callable[[], str],
) -> FixedRule:
    date_text, time_text, zone_text = _fixed_wall_fields(raw)
    stored: FixedRule | None
    if "id" in raw:
        stored = existing_by_id[_given_id(raw["id"])]
    else:
        stored = _stored_by_wall_intent(
            existing_by_id, reserved, claimed, date_text, time_text, zone_text
        )
    if stored is not None and _same_wall_intent(
        stored, date_text, time_text, zone_text
    ):
        return stored
    instant = _future_instant(date_text, time_text, zone_text, now)
    return FixedRule(
        id=new_rule_id(),
        date=date_text,
        time=time_text,
        timezone=zone_text,
        instant=instant,
        activation=now,
    )


def _fixed_wall_fields(raw: Mapping[str, Any]) -> tuple[str, str, str]:
    date_text = _short_text(raw["date"], limit=10)
    if not DATE.fullmatch(date_text):
        raise ValueError("date must be YYYY-MM-DD")
    time_text = _short_text(raw["time"], limit=5)
    if not CLOCK_TIME.fullmatch(time_text):
        raise ValueError("time must be HH:MM")
    zone_text = _short_text(raw["timezone"], limit=MAX_ZONE_NAME_LENGTH)
    return date_text, time_text, zone_text


def _short_text(value: object, *, limit: int) -> str:
    if not isinstance(value, str) or not value or len(value) > limit:
        raise ValueError("A fixed rule field must be a short non-empty string")
    return value


def _given_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("id must be a UUID string")
    try:
        canonical = str(uuid.UUID(value))
    except ValueError:
        raise ValueError("id must be a UUID string") from None
    if canonical != value:
        raise ValueError("id must be a lowercase UUID")
    return value


def _stored_by_wall_intent(
    existing_by_id: Mapping[str, FixedRule],
    reserved: frozenset[str],
    claimed: set[str],
    date_text: str,
    time_text: str,
    zone_text: str,
) -> FixedRule | None:
    """The first stored rule with this wall intent that no input has reserved.

    Rules named by an explicit id are reserved; an id-less input never takes them.
    """
    for rule in existing_by_id.values():
        if (
            rule.id not in reserved
            and rule.id not in claimed
            and _same_wall_intent(rule, date_text, time_text, zone_text)
        ):
            claimed.add(rule.id)
            return rule
    return None


def _same_wall_intent(
    rule: FixedRule, date_text: str, time_text: str, zone_text: str
) -> bool:
    return (
        rule.date == date_text and rule.time == time_text and rule.timezone == zone_text
    )


def _future_instant(
    date_text: str, time_text: str, zone_text: str, now: datetime
) -> datetime:
    """The UTC instant of a new or changed fixed rule, which must be after `now`."""
    try:
        zone = load_zone(zone_text)
        instant = resolve_wall_time(
            calendar_date.fromisoformat(date_text),
            clock_time.fromisoformat(time_text),
            zone,
        )
    except OverflowError as error:
        raise ValueError(
            "The fixed reminder is outside the supported calendar"
        ) from error
    if instant <= now:
        raise ValueError("A new or changed fixed reminder must be in the future")
    return instant


def _reject_duplicates(rules: Sequence[Rule]) -> None:
    keys: set[str] = set()
    instants: set[datetime] = set()
    for rule in rules:
        if isinstance(rule, RelativeRule):
            if rule.key in keys:
                raise ValueError("Duplicate relative reminder")
            keys.add(rule.key)
        else:
            if rule.instant in instants:
                raise ValueError("Two fixed reminders resolve to the same time")
            instants.add(rule.instant)
