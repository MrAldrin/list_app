"""Pure, bounded item-contribution preview; not a dispatch prediction."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from reminders.policies import EffectivePolicy
from reminders.rules import FixedRule, Rule
from reminders.zoned_time import TimeZoneUnavailable, load_zone, resolve_wall_time


@dataclass(frozen=True)
class QuietWindow:
    start: str
    end: str


@dataclass(frozen=True)
class PreviewEntry:
    kind: Literal["rules", "summary"]
    instant: datetime
    keys: tuple[str, ...]
    deferred_until: datetime | None
    local_day: str | None = None


@dataclass(frozen=True)
class PreviewResult:
    entries: tuple[PreviewEntry, ...]
    disabled_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedRule:
    instant: datetime
    key: str
    cutoffs: tuple[datetime, ...]

    @property
    def historically_eligible(self) -> bool:
        return all(self.instant >= cutoff for cutoff in self.cutoffs)


class MissingDueInstant(ValueError):
    """A timed rule has no confirmed due_at."""


def resolve_rule(policy: EffectivePolicy, rule: Rule) -> ResolvedRule:
    """Resolve a trusted rule without applying preview's future-only filter.

    Fixed identities never use the item cycle or selected policy's activation;
    enrollment and lower reset activations remain safety cutoffs.
    """
    if policy.due_date is None:
        raise ValueError("An item needs a due date")
    if isinstance(rule, FixedRule):
        return ResolvedRule(
            rule.instant,
            f"fixed:{rule.id}",
            (
                rule.activation,
                *(
                    a.at
                    for a in policy.relative_activations
                    if a.source not in ("cycle", "device_anchor", policy.source)
                ),
            ),
        )
    day = date.fromisoformat(policy.due_date)
    clock = time.fromisoformat(policy.due_time or policy.all_day_time)
    zone_name = policy.due_timezone if policy.due_time else policy.timezone
    if rule.basis != "calendar" and policy.due_time:
        if policy.due_at is None:
            raise MissingDueInstant("A timed item needs its confirmed instant")
        anchor = policy.due_at
    else:
        if zone_name is None:
            raise ValueError("A due timezone is required")
        zone = load_zone(zone_name)
        if rule.basis == "calendar":
            day -= timedelta(days=rule.amount)
        anchor = resolve_wall_time(day, clock, zone)
    instant = (
        anchor - timedelta(minutes=rule.amount) if rule.basis == "elapsed" else anchor
    )
    return ResolvedRule(
        instant, rule.key, tuple(a.at for a in policy.relative_activations)
    )


def _quiet_end(
    instant: datetime, zone_name: str, quiet: QuietWindow | None
) -> datetime | None:
    if quiet is None:
        return None
    zone = load_zone(zone_name)
    local = instant.astimezone(zone)
    clock = local.time().replace(tzinfo=None)
    start, end = time.fromisoformat(quiet.start), time.fromisoformat(quiet.end)
    if start < end:
        if not start <= clock < end:
            return None
        day = local.date()
    else:
        if clock >= start:
            day = local.date() + timedelta(days=1)
        elif clock < end:
            day = local.date()
        else:
            return None
    return resolve_wall_time(day, end, zone)


def preview_item(
    policy: EffectivePolicy, *, now: datetime, quiet: QuietWindow | None = None
) -> PreviewResult:
    """Next five eligible rule instants or item summary contributions.

    Activation is inclusive; preview is strictly after now. Quiet deferral is
    room-summary eligibility, not a promise of dispatch. Inputs are trusted
    server records, and this function never samples a clock or mutates them.
    """
    if now.utcoffset() is None:
        raise ValueError("now must be aware")
    now = now.astimezone(UTC)
    if policy.disabled_reasons:
        return PreviewResult((), policy.disabled_reasons)
    if policy.due_date is None:
        return PreviewResult((), ("undated",))
    reasons: set[str] = set()
    grouped: dict[datetime, list[str]] = {}
    for rule in policy.rules:
        try:
            resolved = resolve_rule(policy, rule)
            if resolved.instant > now and resolved.historically_eligible:
                grouped.setdefault(resolved.instant, []).append(resolved.key)
        except MissingDueInstant:
            reasons.add("missing_due_instant")
        except TimeZoneUnavailable:
            reasons.add("timezone_unavailable")
        except (OverflowError, ValueError):
            reasons.add("calendar_out_of_range")
    entries: list[PreviewEntry] = []
    for instant, keys in grouped.items():
        try:
            deferred = _quiet_end(instant, policy.timezone, quiet)
        except TimeZoneUnavailable:
            reasons.add("timezone_unavailable")
            deferred = None
        except (OverflowError, ValueError):
            reasons.add("calendar_out_of_range")
            deferred = None
        entries.append(PreviewEntry("rules", instant, tuple(sorted(keys)), deferred))
    if policy.summary_enabled:
        try:
            zone = load_zone(policy.timezone)
            cutoff = max([now, *(a.at for a in policy.summary_activations)])
            today = cutoff.astimezone(zone).date()
            due_day = (
                policy.due_at.astimezone(zone).date()
                if policy.due_time and policy.due_at is not None
                else date.fromisoformat(policy.due_date)
            )
            first_due_day = (
                max(date.min, due_day - timedelta(days=1))
                if due_day > date.min
                else date.min
            )
            day = max(today, first_due_day)
            clock = time.fromisoformat(policy.summary_time)
            for _ in range(6):
                instant = resolve_wall_time(day, clock, zone)
                if instant > now and all(
                    instant >= a.at for a in policy.summary_activations
                ):
                    entries.append(
                        PreviewEntry(
                            "summary",
                            instant,
                            (),
                            _quiet_end(instant, policy.timezone, quiet),
                            day.isoformat(),
                        )
                    )
                if day == date.max:
                    break
                day += timedelta(days=1)
        except TimeZoneUnavailable:
            reasons.add("timezone_unavailable")
        except (OverflowError, ValueError):
            reasons.add("calendar_out_of_range")
    entries.sort(key=lambda entry: (entry.instant, entry.kind, entry.keys))
    return PreviewResult(tuple(entries[:5]), tuple(sorted(reasons)))
