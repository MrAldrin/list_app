"""Own-installation policy storage and the concrete, read-only effective policy.

Call *_locked inside the caller's database transaction, after room/target access
checks. Enrollment.mode is the sole room preset. Reset rows are tombstones: their
activation survives inheritance, so resetting never reopens earlier offsets.
No preview, occurrence generation, transport or grant activation lives here.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from database_setup import db
from reminders import identity
from reminders.rules import FixedRule, RelativeRule, Rule, normalize_rules
from reminders.zoned_time import format_utc

Scope = Literal["room", "list", "item"]
Preset = Literal["quiet", "daily_summary", "scheduled", "custom"]
PolicyState = Literal["inherit", "off", "replace"]
SCHEDULED = (RelativeRule("calendar", 1), RelativeRule("at_due", 0))


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class Policy:
    id: int | None
    scope: Scope
    state: PolicyState
    preset: Preset | None
    summary_enabled: bool
    rules: tuple[Rule, ...]
    revision: int
    activated_at: datetime | None


@dataclass(frozen=True)
class Activation:
    source: str
    at: datetime


@dataclass(frozen=True)
class EffectivePolicy:
    """Typed input for the next pure preview milestone; never authorizes a send.

    rules include stored FixedRule UUID/instant/activation, never re-resolved.
    relative_activations applies only to relative rules; fixed rules use their
    own activation plus enrollment/safety checks, independently of due cycles.
    summary_activations excludes the item cycle and date-only device anchor.
    Revisions are labeled room/list/item/enrollment/device; 0 means no policy row.
    """

    source: Scope
    state: PolicyState
    preset: Preset | None
    rules: tuple[Rule, ...]
    revisions: tuple[tuple[str, int], ...]
    relative_activations: tuple[Activation, ...]
    summary_activations: tuple[Activation, ...]
    summary_enabled: bool
    summary_time: str
    timezone: str
    all_day_time: str
    grant_state: str
    disabled_reasons: tuple[str, ...]
    due_date: str | None
    due_time: str | None
    due_timezone: str | None
    due_at: datetime | None
    due_cycle: str | None

    @property
    def relative_cutoff(self) -> datetime | None:
        return max((entry.at for entry in self.relative_activations), default=None)


def _row_locked(
    installation_id: int, room_id: int, scope: Scope, target_id: int | None
):
    column = {"room": "room_id", "list": "list_id", "item": "item_id"}[scope]
    return db.execute(
        f"SELECT id, state, preset, summary_enabled, revision, activated_at "
        f"FROM reminder_policies WHERE installation_id = ? AND room_id = ? "
        f"AND scope = ? AND {column} = ?",
        (installation_id, room_id, scope, room_id if scope == "room" else target_id),
    ).fetchone()


def _rules_locked(policy_id: int) -> tuple[Rule, ...]:
    rows = db.execute(
        "SELECT kind, basis, amount, fixed_id, wall_date, wall_time, timezone, "
        "instant, activation FROM reminder_policy_rules WHERE policy_id = ? "
        "ORDER BY position",
        (policy_id,),
    ).fetchall()
    return tuple(
        RelativeRule(row[1], row[2])
        if row[0] == "relative"
        else FixedRule(row[3], row[4], row[5], row[6], instant(row[7]), instant(row[8]))
        for row in rows
    )


def validate_target_locked(room_id: int, scope: Scope, target_id: int | None) -> None:
    """Reject another room's resource even when no policy row exists yet."""
    if scope == "room" and target_id is None:
        return
    query = {
        "list": "SELECT 1 FROM lists WHERE id = ? AND room_id = ?",
        "item": "SELECT 1 FROM items i JOIN lists l ON l.id = i.list_id "
        "WHERE i.id = ? AND l.room_id = ?",
    }.get(scope)
    if query is None or db.execute(query, (target_id, room_id)).fetchone() is None:
        raise ValueError("Unavailable policy target")


def policy_locked(
    installation_id: int, room_id: int, scope: Scope, target_id: int | None = None
) -> Policy:
    validate_target_locked(room_id, scope, target_id)
    row = _row_locked(installation_id, room_id, scope, target_id)
    enrollment = identity.enrollment_row_locked(installation_id, room_id)
    if enrollment is None:
        raise ValueError("An enrollment is required")
    preset = enrollment["mode"] if scope == "room" else (row[2] if row else None)
    if row is None:
        return Policy(
            None,
            scope,
            "replace" if scope == "room" else "inherit",
            preset,
            preset == "daily_summary",
            SCHEDULED if preset == "scheduled" else (),
            0,
            instant(enrollment["policy_activated_at"]) if scope == "room" else None,
        )
    return Policy(
        row[0],
        scope,
        row[1],
        preset,
        bool(row[3]),
        _rules_locked(row[0]),
        row[4],
        instant(row[5]),
    )


def _save_locked(
    installation_id: int,
    room_id: int,
    scope: Scope,
    target_id: int | None,
    state: PolicyState,
    preset: Preset | None,
    summary: bool,
    rules: tuple[Rule, ...],
    now: datetime,
) -> None:
    row = _row_locked(installation_id, room_id, scope, target_id)
    if row is None:
        cursor = db.execute(
            "INSERT INTO reminder_policies (installation_id, room_id, scope, list_id, "
            "item_id, state, preset, summary_enabled, revision, activated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (
                installation_id,
                room_id,
                scope,
                target_id if scope == "list" else None,
                target_id if scope == "item" else None,
                state,
                None if scope == "room" else preset,
                int(summary),
                format_utc(now),
            ),
        )
        policy_id = cursor.lastrowid
    else:
        policy_id = row[0]
        db.execute(
            "UPDATE reminder_policies SET state = ?, preset = ?, summary_enabled = ?, "
            "revision = revision + 1, activated_at = ? WHERE id = ?",
            (
                state,
                None if scope == "room" else preset,
                int(summary),
                format_utc(now),
                policy_id,
            ),
        )
        db.execute(
            "DELETE FROM reminder_policy_rules WHERE policy_id = ?", (policy_id,)
        )
    for position, rule in enumerate(rules):
        values = (
            ("relative", rule.basis, rule.amount, None, None, None, None, None, None)
            if isinstance(rule, RelativeRule)
            else (
                "fixed",
                None,
                None,
                rule.id,
                rule.date,
                rule.time,
                rule.timezone,
                format_utc(rule.instant),
                format_utc(rule.activation),
            )
        )
        db.execute(
            "INSERT INTO reminder_policy_rules (policy_id, position, kind, basis, "
            "amount, fixed_id, wall_date, wall_time, timezone, instant, activation) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (policy_id, position, *values),
        )


def replace_policy_locked(
    installation_id: int,
    room_id: int,
    scope: Scope,
    target_id: int | None,
    *,
    state: PolicyState,
    preset: Preset | None,
    inputs: list[dict[str, Any]],
    summary_enabled: bool,
    summary_time: str | None,
    now: datetime,
) -> Policy:
    """Validated full replacement; unchanged normalized saves are semantic no-ops."""
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("now must be an aware datetime")
    if state not in ("inherit", "off", "replace") or type(summary_enabled) is not bool:
        raise ValueError("Invalid policy state or summary flag")
    if summary_time is not None:
        from reminders.due_schedule import CLOCK_TIME

        if not isinstance(summary_time, str) or not CLOCK_TIME.fullmatch(summary_time):
            raise ValueError("Summary time must be HH:MM")
    current = policy_locked(installation_id, room_id, scope, target_id)
    enrollment = identity.enrollment_row_locked(installation_id, room_id)
    assert enrollment is not None
    if scope == "room" and (state != "replace" or preset is None):
        raise ValueError("The room default requires a preset replacement")
    if state != "replace":
        if preset is not None or inputs or summary_enabled:
            raise ValueError("Off/inherit takes no preset, rules or summary")
        rules = ()
        summary = False
    elif preset == "custom":
        rules = normalize_rules(
            inputs,
            existing_rules=tuple(
                rule for rule in current.rules if isinstance(rule, FixedRule)
            ),
            now=now,
        )
        summary = summary_enabled
    elif preset in ("quiet", "daily_summary", "scheduled"):
        if inputs or summary_enabled:
            raise ValueError("Only custom accepts rules and summary_enabled")
        rules = SCHEDULED if preset == "scheduled" else ()
        summary = preset == "daily_summary"
    else:
        raise ValueError("A replacement requires a preset")
    if summary_time is not None and scope != "room":
        raise ValueError("Summary time belongs to the room enrollment")
    changed_time = (
        summary_time is not None and summary_time != enrollment["summary_time"]
    )
    if (
        (current.state, current.preset, current.summary_enabled)
        == (state, preset, summary)
        and frozenset(current.rules) == frozenset(rules)
        and not changed_time
    ):
        return current
    _save_locked(
        installation_id, room_id, scope, target_id, state, preset, summary, rules, now
    )
    if scope == "room":
        db.execute(
            "UPDATE reminder_enrollments SET mode = ?, summary_time = ?, "
            "policy_activated_at = ?, summary_activated_at = ?, revision = revision + 1 "
            "WHERE installation_id = ? AND room_id = ?",
            (
                preset,
                summary_time or enrollment["summary_time"],
                format_utc(now),
                format_utc(now) if changed_time else enrollment["summary_activated_at"],
                installation_id,
                room_id,
            ),
        )
    return policy_locked(installation_id, room_id, scope, target_id)


def sync_enrollment_policy_locked(
    installation_id: int,
    room_id: int,
    previous_mode: str,
    mode: str,
    summary_changed: bool,
    now: datetime,
) -> None:
    """Existing enrollment writes select presets atomically, without granting access."""
    if previous_mode == mode and not summary_changed:
        return
    current = policy_locked(installation_id, room_id, "room")
    rules = (
        current.rules
        if previous_mode == mode
        else (SCHEDULED if mode == "scheduled" else ())
    )
    summary = (
        current.summary_enabled if previous_mode == mode else mode == "daily_summary"
    )
    _save_locked(
        installation_id, room_id, "room", None, "replace", None, summary, rules, now
    )
    db.execute(
        "UPDATE reminder_enrollments SET policy_activated_at = ?, "
        "summary_activated_at = CASE WHEN ? THEN ? ELSE summary_activated_at END "
        "WHERE installation_id = ? AND room_id = ?",
        (format_utc(now), summary_changed, format_utc(now), installation_id, room_id),
    )


def resolve_policy_locked(
    installation_id: int, room_id: int, scope: Scope, target_id: int | None = None
) -> tuple[Policy, tuple[Policy, ...], tuple[Activation, ...]]:
    """Selected replacement, scope-to-room chain and applicable durable cutoffs."""
    own = policy_locked(installation_id, room_id, scope, target_id)
    chain = [own]
    if scope == "item":
        list_id = db.execute(
            "SELECT list_id FROM items WHERE id = ?", (target_id,)
        ).fetchone()[0]
        chain.append(policy_locked(installation_id, room_id, "list", list_id))
    if scope != "room":
        chain.append(policy_locked(installation_id, room_id, "room"))
    enrollment = identity.enrollment_row_locked(installation_id, room_id)
    assert enrollment is not None
    applicable = [Activation("enrollment", instant(enrollment["activated_at"]))]
    for policy in chain:
        if policy.activated_at is not None:
            applicable.append(Activation(policy.scope, policy.activated_at))
        if policy.state != "inherit":
            return policy, tuple(chain), tuple(applicable)
    raise RuntimeError("Room policy must replace inheritance")


def effective_policy_locked(
    installation_id: int, room_id: int, item_id: int, *, now: datetime | None = None
) -> EffectivePolicy:
    """Read own effective policy for an item; fail closed on wrong room/installation.

    Background consumers must also revalidate the grant immediately before work.
    This function uses the authoritative saved-grant validator, not stored status.
    Only the selected policy and reset rows below it contribute policy cutoffs.
    """
    item = db.execute(
        "SELECT i.list_id, i.date, i.due_time, i.due_timezone, i.due_at, i.due_cycle, "
        "i.due_cycle_started_at, i.done FROM items i JOIN lists l ON l.id = i.list_id "
        "WHERE i.id = ? AND l.room_id = ?",
        (item_id, room_id),
    ).fetchone()
    enrollment = identity.enrollment_row_locked(installation_id, room_id)
    if item is None or enrollment is None:
        raise ValueError("Unavailable policy target")
    device = identity.installation_settings_locked(installation_id)
    selected, chain, cutoffs = resolve_policy_locked(
        installation_id, room_id, "item", item_id
    )
    applicable = list(cutoffs)
    summary_activations = (
        *applicable,
        Activation("summary_time", instant(enrollment["summary_activated_at"])),
        Activation("device_timezone", instant(device["timezone_activated_at"])),
    )
    if item[6] is not None:
        applicable.append(Activation("cycle", instant(item[6])))
    if item[2] is None:
        applicable.append(
            Activation("device_anchor", instant(device["anchor_activated_at"]))
        )
    grant = identity.saved_grant_state_locked(installation_id, room_id, now=now)
    disabled = []
    if grant != identity.STATUS_ACTIVE:
        disabled.append(grant)
    if device["paused"]:
        disabled.append("device_paused")
    if selected.state == "off" or selected.preset == "quiet":
        disabled.append("policy_off")
    if item[1] is None:
        disabled.append("undated")
    if item[7]:
        disabled.append("completed")
    return EffectivePolicy(
        selected.scope,
        selected.state,
        selected.preset,
        selected.rules,
        (
            *((p.scope, p.revision) for p in chain),
            ("enrollment", enrollment["revision"]),
            ("device", device["revision"]),
        ),
        tuple(applicable),
        summary_activations,
        selected.summary_enabled,
        enrollment["summary_time"],
        device["timezone"],
        device["all_day_time"],
        grant,
        tuple(disabled),
        item[1],
        item[2],
        item[3],
        instant(item[4]) if item[4] else None,
        item[5],
    )
