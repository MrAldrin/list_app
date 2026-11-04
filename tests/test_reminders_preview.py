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


def test_quiet_interval_uses_utc_boundaries_across_dst():
    from reminders.preview import _quiet_end

    # First 02:30 is 00:30Z; the second occurrence never reopens that interval.
    cases = [
        ("22:00", "02:30", "2026-10-24T19:59", None),
        ("22:00", "02:30", "2026-10-24T20:00", "2026-10-25T00:30"),
        ("22:00", "02:30", "2026-10-25T00:15", "2026-10-25T00:30"),
        ("22:00", "02:30", "2026-10-25T00:29:59", "2026-10-25T00:30"),
        ("22:00", "02:30", "2026-10-25T00:30", None),
        ("22:00", "02:30", "2026-10-25T00:45", None),
        ("22:00", "02:30", "2026-10-25T01:15", None),
        ("22:00", "02:30", "2026-10-25T01:30", None),
        ("02:30", "04:00", "2026-10-25T00:29:59", None),
        ("02:30", "04:00", "2026-10-25T00:30", "2026-10-25T03:00"),
        ("02:30", "04:00", "2026-10-25T00:45", "2026-10-25T03:00"),
        ("02:30", "04:00", "2026-10-25T01:15", "2026-10-25T03:00"),
        ("02:30", "04:00", "2026-10-25T01:30", "2026-10-25T03:00"),
        ("02:30", "04:00", "2026-10-25T02:59:59", "2026-10-25T03:00"),
        ("02:30", "04:00", "2026-10-25T03:00", None),
        ("02:30", "01:30", "2026-10-25T00:29:59", None),
        ("02:30", "01:30", "2026-10-25T00:30", "2026-10-26T00:30"),
        ("02:30", "01:30", "2026-10-25T01:15", "2026-10-26T00:30"),
        ("22:00", "02:30", "2026-03-29T00:59", "2026-03-29T01:00"),
        ("22:00", "02:30", "2026-03-29T01:00", None),
        ("02:30", "04:00", "2026-03-29T00:59", None),
        ("02:30", "04:00", "2026-03-29T01:00", "2026-03-29T02:00"),
        ("09:00", "17:00", "2026-02-01T08:00", "2026-02-01T16:00"),
        ("09:00", "17:00", "2026-02-01T16:00", None),
        ("22:00", "08:00", "2026-02-01T21:00", "2026-02-02T07:00"),
        ("22:00", "08:00", "2026-02-02T07:00", None),
    ]
    for start, end, original, expected in cases:
        instant = dt(original)
        result = _quiet_end(instant, "Europe/Oslo", QuietWindow(start, end))
        assert result == (dt(expected) if expected else None), (start, end, original)
        assert result is None or result > instant
    assert _quiet_end(dt("2026-10-25T01:15"), "Europe/Oslo", None) is None


def test_quiet_rejects_equal_times_and_handles_calendar_bounds():
    import pytest

    from reminders.preview import _quiet_end

    with pytest.raises(ValueError):
        _quiet_end(dt("2026-01-01T12:00"), "UTC", QuietWindow("09:00", "09:00"))
    assert (
        _quiet_end(dt("0001-01-01T01:00"), "UTC", QuietWindow("22:00", "08:00")) is None
    )
    assert _quiet_end(
        dt("9999-12-31T01:00"), "UTC", QuietWindow("22:00", "08:00")
    ) == dt("9999-12-31T08:00")
    with pytest.raises(OverflowError):
        _quiet_end(dt("9999-12-31T23:00"), "UTC", QuietWindow("22:00", "08:00"))


def test_fold_quiet_rule_and_summary_keep_original_instants():
    second = dt("2026-10-25T01:15")
    fixed = FixedRule(
        "stable", "2026-10-25", "02:15", "Europe/Oslo", second, dt("2026-01-01T00:00")
    )
    p = policy(
        due_date="2026-10-25",
        due_time=None,
        due_timezone=None,
        due_at=None,
        rules=(fixed,),
        summary_enabled=True,
        summary_time="02:15",
    )
    result = preview_item(
        p, now=dt("2026-10-24T00:00"), quiet=QuietWindow("22:00", "02:30")
    )
    same_day = [
        e for e in result.entries if e.instant.date().isoformat() == "2026-10-25"
    ]
    assert [(e.kind, e.instant, e.deferred_until) for e in same_day] == [
        ("summary", dt("2026-10-25T00:15"), dt("2026-10-25T00:30")),
        ("rules", second, None),
    ]
    assert all(
        e.deferred_until is None or e.deferred_until > e.instant for e in result.entries
    )


def test_missing_confirmed_timed_instant_does_not_resolve_wall():
    p = policy(
        due_at=None,
        rules=(RelativeRule("at_due", 0), RelativeRule("elapsed", 60)),
        summary_enabled=True,
    )
    result = preview_item(p, now=dt("2026-03-01T00:00"))
    assert result.disabled_reasons == ("missing_due_instant",)
    assert result.entries and all(e.kind == "summary" for e in result.entries)
