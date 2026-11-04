"""Pure preview uses confirmed instants and historical activation."""

from dataclasses import replace
from datetime import UTC, datetime

from reminders.policies import Activation, EffectivePolicy
from reminders.preview import QuietWindow, preview_item
from reminders.rules import FixedRule, RelativeRule


def dt(text):
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def policy(**changes):
    value = EffectivePolicy(
        source="room",
        state="replace",
        preset="custom",
        rules=(),
        revisions=(),
        relative_activations=(Activation("enrollment", dt("2026-01-01T00:00")),),
        summary_activations=(Activation("enrollment", dt("2026-01-01T00:00")),),
        summary_enabled=False,
        summary_time="09:00",
        timezone="Europe/Oslo",
        all_day_time="09:00",
        grant_state="active",
        disabled_reasons=(),
        due_date="2026-03-30",
        due_time="09:00",
        due_timezone="Europe/Oslo",
        due_at=dt("2026-03-30T07:00"),
        due_cycle="cycle",
    )
    return replace(value, **changes)


def test_stored_instant_elapsed_and_calendar_across_dst():
    p = policy(
        due_at=dt("2026-03-30T08:00"),
        rules=(
            RelativeRule("at_due", 0),
            RelativeRule("elapsed", 1440),
            RelativeRule("calendar", 1),
        ),
    )
    result = preview_item(p, now=dt("2026-03-27T00:00"))
    assert [(e.instant, e.keys) for e in result.entries] == [
        (dt("2026-03-29T07:00"), ("calendar:1d",)),
        (dt("2026-03-29T08:00"), ("elapsed:1440m",)),
        (dt("2026-03-30T08:00"), ("at-due",)),
    ]
    assert preview_item(p, now=dt("2026-03-27T00:00")) == result


def test_date_only_gap_fold_and_default_anchor():
    p = policy(
        due_date="2026-03-29",
        due_time=None,
        due_timezone=None,
        due_at=None,
        all_day_time="02:30",
        rules=(RelativeRule("at_due", 0),),
    )
    assert preview_item(p, now=dt("2026-03-01T00:00")).entries[0].instant == dt(
        "2026-03-29T01:00"
    )
    p = replace(p, due_date="2026-10-25")
    assert preview_item(p, now=dt("2026-03-01T00:00")).entries[0].instant == dt(
        "2026-10-25T00:30"
    )
    p = replace(p, all_day_time="09:00")
    assert preview_item(p, now=dt("2026-03-01T00:00")).entries[0].instant == dt(
        "2026-10-25T08:00"
    )


def test_fixed_independent_of_cycle_and_coalescing_cutoffs():
    instant = dt("2026-03-30T07:00")
    fixed = FixedRule(
        "stable", "2026-03-30", "09:00", "missing/zone", instant, dt("2026-01-01T00:00")
    )
    p = policy(
        rules=(fixed, RelativeRule("at_due", 0)),
        relative_activations=(
            Activation("enrollment", instant),
            Activation("cycle", instant),
        ),
    )
    result = preview_item(p, now=dt("2026-03-29T00:00"))
    assert result.entries[0].keys == ("at-due", "fixed:stable")
    p = replace(
        p,
        relative_activations=(
            *p.relative_activations,
            Activation("cycle", dt("2026-03-30T08:00")),
        ),
    )
    assert preview_item(p, now=dt("2026-03-29T00:00")).entries[0].keys == (
        "fixed:stable",
    )
    assert not preview_item(p, now=instant).entries


def test_summary_bounded_quiet_and_disabled():
    p = policy(
        due_date="2099-01-10",
        due_time=None,
        due_at=None,
        due_timezone=None,
        summary_enabled=True,
        summary_time="23:00",
    )
    result = preview_item(
        p, now=dt("2026-01-01T00:00"), quiet=QuietWindow("22:00", "08:00")
    )
    assert len(result.entries) == 5
    assert result.entries[0].local_day == "2099-01-09"
    assert result.entries[0].deferred_until == dt("2099-01-10T07:00")
    assert (
        preview_item(
            replace(p, disabled_reasons=("needs_resume",)), now=dt("2026-01-01T00:00")
        ).entries
        == ()
    )


def test_fixed_available_when_date_only_zone_missing():
    instant = dt("2026-03-30T07:00")
    fixed = FixedRule(
        "stable", "2026-03-30", "09:00", "missing/zone", instant, dt("2026-01-01T00:00")
    )
    p = policy(
        timezone="missing/zone",
        due_time=None,
        due_timezone=None,
        due_at=None,
        rules=(fixed, RelativeRule("at_due", 0)),
    )
    result = preview_item(p, now=dt("2026-03-01T00:00"))
    assert result.entries[0].keys == ("fixed:stable",)
    assert result.disabled_reasons == ("timezone_unavailable",)


def test_far_future_fixed_not_cut_off_by_summary_search():
    instant = dt("2200-03-30T07:00")
    fixed = FixedRule(
        "stable", "2200-03-30", "09:00", "UTC", instant, dt("2026-01-01T00:00")
    )
    p = policy(
        rules=(fixed,),
        due_date="2300-01-01",
        due_time=None,
        due_timezone=None,
        due_at=None,
        summary_enabled=True,
    )
    result = preview_item(p, now=dt("2026-01-01T00:00"))
    assert result.entries[0].instant == instant
    assert len(result.entries) == 5


def test_historical_eligibility_is_separate_from_future_preview():
    from reminders.preview import resolve_rule

    instant = dt("2026-03-30T07:00")
    rule = RelativeRule("at_due", 0)
    p = policy(rules=(rule,), relative_activations=(Activation("cycle", instant),))
    resolved = resolve_rule(p, rule)
    assert resolved.historically_eligible
    assert preview_item(p, now=instant).entries == ()
    p = replace(p, relative_activations=(Activation("cycle", dt("2026-03-30T07:01")),))
    assert not resolve_rule(p, rule).historically_eligible
