"""Private policy replacements and applicable durable activation cutoffs."""

from datetime import UTC, datetime, timedelta

import pytest
from api_helpers import new_id

from database_crud import transaction
from database_setup import db
from reminders import identity, policies
from reminders.due_schedule import relative_rule_is_active
from reminders.rules import FixedRule, RelativeRule

START = datetime(2026, 11, 4, 10, tzinfo=UTC)


@pytest.fixture
def policy_home(room, monkeypatch):
    room_id, slug, client = room
    clock = [START]
    monkeypatch.setattr(identity, "current_time", lambda: clock[0])
    result = client.post(
        f"/api/v1/rooms/{slug}/reminders/enrollment",
        json={"op_id": new_id(), "timezone": "Europe/Oslo", "mode": "scheduled"},
    )
    assert result.status_code == 200, result.text
    installation_id = db.execute("SELECT id FROM reminder_installations").fetchone()[0]
    list_id = db.execute(
        "SELECT id FROM lists WHERE room_id = ?", (room_id,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO items (name, name_key, done, list_id, date, due_cycle, due_cycle_started_at) "
        "VALUES ('policy item', 'policy item', 0, ?, '2026-11-10', ?, ?)",
        (list_id, new_id(), "2026-11-04T09:00:00.000Z"),
    )
    item_id = db.execute(
        "SELECT id FROM items WHERE list_id = ?", (list_id,)
    ).fetchone()[0]
    db.commit()
    return installation_id, room_id, list_id, item_id, clock, client, slug


def put(
    home,
    scope="room",
    *,
    state="replace",
    preset="scheduled",
    inputs=None,
    summary=False,
    summary_time=None,
):
    installation, room, list_id, item_id, clock, _client, _slug = home
    with transaction(write=True):
        return policies.replace_policy_locked(
            installation,
            room,
            scope,
            {"room": None, "list": list_id, "item": item_id}[scope],
            state=state,
            preset=preset,
            inputs=inputs or [],
            summary_enabled=summary,
            summary_time=summary_time,
            now=clock[0],
        )


def effective(home):
    with transaction():
        return policies.effective_policy_locked(home[0], home[1], home[3])


def test_presets_and_custom_explicit_summary(policy_home):
    home = policy_home
    assert effective(home).rules == policies.SCHEDULED
    for preset, summary, rules in (
        ("quiet", False, ()),
        ("daily_summary", True, ()),
        ("scheduled", False, policies.SCHEDULED),
    ):
        put(home, preset=preset)
        value = effective(home)
        assert (value.preset, value.summary_enabled, value.rules) == (
            preset,
            summary,
            rules,
        )
        assert identity.enrollment_row_locked(home[0], home[1])["mode"] == preset
    put(
        home,
        preset="custom",
        summary=True,
        inputs=[{"kind": "relative", "amount": 7, "unit": "days"}],
    )
    assert effective(home).summary_enabled
    assert effective(home).rules == (RelativeRule("calendar", 7),)


def test_override_replaces_default_even_quiet_but_safety_wins(policy_home):
    home = policy_home
    put(home, preset="quiet")
    put(home, "list", preset="scheduled")
    assert effective(home).source == "list"
    assert not effective(home).disabled_reasons
    put(
        home,
        "item",
        preset="custom",
        inputs=[{"kind": "relative", "amount": 2, "unit": "hours"}],
    )
    assert effective(home).rules == (RelativeRule("elapsed", 120),)
    with transaction(write=True):
        identity.update_installation_settings_locked(home[0], {"paused": True})
        identity.update_enrollment_locked(home[0], home[1], {"status": "opted_out"})
    assert set(effective(home).disabled_reasons) == {"device_paused", "opted_out"}
    put(home, "item", preset="scheduled")
    assert set(effective(home).disabled_reasons) == {"device_paused", "opted_out"}


def test_off_is_not_inherit_and_reset_retains_cutoff_and_revision(policy_home):
    home = policy_home
    put(home, "list", state="off", preset=None)
    assert effective(home).state == "off"
    assert effective(home).rules == ()
    home[4][0] += timedelta(hours=1)
    reset = put(home, "list", state="inherit", preset=None)
    assert reset.revision == 2
    value = effective(home)
    assert value.source == "room"
    assert value.relative_cutoff == home[4][0]
    assert {a.source for a in value.relative_activations} == {
        "cycle",
        "enrollment",
        "room",
        "list",
        "device_anchor",
    }
    assert not relative_rule_is_active(
        START + timedelta(minutes=5), [value.relative_cutoff]
    )
    home[4][0] += timedelta(hours=1)
    assert put(home, "list", state="inherit", preset=None) == reset


def test_only_applicable_defaults_and_resets_affect_override(policy_home):
    home = policy_home
    put(home, "list", preset="scheduled")
    original = effective(home).relative_cutoff
    home[4][0] += timedelta(hours=1)
    put(
        home,
        preset="custom",
        inputs=[{"kind": "relative", "amount": 7, "unit": "days"}],
    )
    assert effective(home).relative_cutoff == original
    assert "room" not in {a.source for a in effective(home).relative_activations}
    put(home, "item", preset="scheduled")
    item_cutoff = effective(home).relative_cutoff
    home[4][0] += timedelta(hours=1)
    put(home, "list", state="inherit", preset=None)
    assert effective(home).relative_cutoff == item_cutoff
    assert "list" not in {a.source for a in effective(home).relative_activations}


def test_noop_normalization_keeps_revision_and_activation(policy_home):
    home = policy_home
    first = put(
        home,
        preset="custom",
        inputs=[{"kind": "relative", "amount": 60, "unit": "minutes"}],
    )
    enrollment = identity.enrollment_row_locked(home[0], home[1])
    home[4][0] += timedelta(hours=2)
    second = put(
        home,
        preset="custom",
        inputs=[{"kind": "relative", "amount": 1, "unit": "hours"}],
    )
    assert second == first
    assert identity.enrollment_row_locked(home[0], home[1]) == enrollment


def test_fixed_roundtrip_keeps_confirmed_past_identity_without_zone_lookup(
    policy_home, monkeypatch
):
    home = policy_home
    raw = {
        "kind": "fixed",
        "date": "2026-11-05",
        "time": "02:30",
        "timezone": "Europe/Oslo",
    }
    first = put(home, "item", preset="custom", inputs=[raw])
    fixed = first.rules[0]
    assert isinstance(fixed, FixedRule)
    home[4][0] += timedelta(days=2)
    monkeypatch.setattr(
        "reminders.rules.load_zone",
        lambda _: pytest.fail("unchanged fixed re-resolved"),
    )
    assert put(home, "item", preset="custom", inputs=[raw]) == first
    assert put(home, "item", preset="custom", inputs=[{**raw, "id": fixed.id}]) == first
    db.execute(
        "UPDATE items SET date = '2026-12-01', due_cycle = ?, due_cycle_started_at = ? WHERE id = ?",
        (new_id(), "2026-11-06T10:00:00Z", home[3]),
    )
    db.commit()
    assert effective(home).rules == (fixed,)


def test_fixed_id_from_another_scope_is_rejected(policy_home):
    home = policy_home
    raw = {
        "kind": "fixed",
        "date": "2028-11-05",
        "time": "02:30",
        "timezone": "Europe/Oslo",
    }
    fixed = put(home, "list", preset="custom", inputs=[raw]).rules[0]
    with pytest.raises(ValueError, match="Unknown fixed"):
        put(home, "item", preset="custom", inputs=[{**raw, "id": fixed.id}])
    assert effective(home).source == "list"


def test_device_anchor_applies_to_date_only_not_timed_and_unrelated_edits_do_not_activate(
    policy_home,
):
    home = policy_home
    before = effective(home).relative_cutoff
    home[4][0] += timedelta(hours=1)
    with transaction(write=True):
        identity.update_installation_settings_locked(
            home[0], {"content_privacy": "names", "daily_cap": 11}
        )
    assert effective(home).relative_cutoff == before
    with transaction(write=True):
        identity.update_installation_settings_locked(
            home[0], {"timezone": "UTC", "all_day_time": "10:00"}
        )
    assert effective(home).relative_cutoff == home[4][0]
    db.execute(
        "UPDATE items SET due_time = '12:00', due_timezone = 'UTC', due_at = '2026-11-10T12:00:00.000Z' WHERE id = ?",
        (home[3],),
    )
    db.commit()
    assert effective(home).relative_cutoff == before
    assert effective(home).due_at == datetime(2026, 11, 10, 12, tzinfo=UTC)


def test_preferences_mode_summary_changes_activate_policy_not_enrollment(policy_home):
    home = policy_home
    enrollment_activation = identity.enrollment_row_locked(home[0], home[1])[
        "activated_at"
    ]
    home[4][0] += timedelta(hours=1)
    with transaction(write=True):
        identity.update_enrollment_locked(home[0], home[1], {"mode": "daily_summary"})
    assert effective(home).summary_enabled
    assert effective(home).relative_cutoff == home[4][0]
    home[4][0] += timedelta(hours=1)
    with transaction(write=True):
        identity.update_enrollment_locked(home[0], home[1], {"summary_time": "11:00"})
    assert effective(home).relative_cutoff == home[4][0]
    assert (
        identity.enrollment_row_locked(home[0], home[1])["activated_at"]
        == enrollment_activation
    )
    value = effective(home)
    home[4][0] += timedelta(hours=1)
    with transaction(write=True):
        identity.update_enrollment_locked(
            home[0], home[1], {"mode": "daily_summary", "summary_time": "11:00"}
        )
    assert effective(home) == value


def test_active_post_mode_change_activates_policy_but_not_resume_cutoff(policy_home):
    home = policy_home
    _installation, _room, _list, _item, clock, client, slug = home
    clock[0] += timedelta(hours=1)
    before = identity.enrollment_row_locked(home[0], home[1])
    response = client.post(
        f"/api/v1/rooms/{slug}/reminders/enrollment",
        json={
            "op_id": new_id(),
            "base_revision": before["revision"],
            "mode": "daily_summary",
        },
    )
    assert response.status_code == 200, response.text
    assert effective(home).relative_cutoff == clock[0]
    assert (
        identity.enrollment_row_locked(home[0], home[1])["activated_at"]
        == before["activated_at"]
    )
    assert effective(home).rules == ()


def test_draft_policy_cannot_resume_revoked_grant_and_resume_preserves_rules(
    policy_home,
):
    home = policy_home
    with transaction(write=True):
        identity.disable_room_enrollments_locked(home[1])
    raw = {"kind": "fixed", "date": "2027-02-01", "time": "09:00", "timezone": "UTC"}
    saved = put(home, "item", preset="custom", inputs=[raw])
    assert "needs_resume" in effective(home).disabled_reasons
    home[4][0] += timedelta(hours=1)
    enrollment = identity.enrollment_row_locked(home[0], home[1])
    response = home[5].post(
        f"/api/v1/rooms/{home[6]}/reminders/enrollment",
        json={"op_id": new_id(), "base_revision": enrollment["revision"]},
    )
    assert response.status_code == 200, response.text
    assert effective(home).rules == saved.rules
    assert effective(home).relative_cutoff == home[4][0]
    assert effective(home).grant_state == "active"


def test_effective_wrong_room_installation_and_undated_completed(policy_home):
    home = policy_home
    for install, room, item in (
        (home[0], -1, home[3]),
        (-1, home[1], home[3]),
        (home[0], home[1], -1),
    ):
        with transaction(), pytest.raises(ValueError, match="Unavailable"):
            policies.effective_policy_locked(install, room, item)
    db.execute(
        "UPDATE items SET date = NULL, due_cycle = NULL, due_cycle_started_at = NULL, done = 1 WHERE id = ?",
        (home[3],),
    )
    db.commit()
    assert set(effective(home).disabled_reasons) == {"undated", "completed"}


def test_policy_replacement_inheritance_revision_and_replay(policy_home):
    _, room, list_id, item_id, _clock, client, slug = policy_home
    base = f"/api/v1/rooms/{slug}/reminders"
    list_url = f"{base}/lists/{list_id}/policy"
    item_url = f"{base}/items/{item_id}/policy"
    before_seq = db.execute(
        "SELECT change_seq FROM rooms WHERE id = ?", (room,)
    ).fetchone()[0]
    body = {"op_id": new_id(), "base_revision": 0, "state": "off"}
    first = client.put(list_url, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["policy"]["revision"] == 1
    assert client.get(item_url).json()["effective"]["state"] == "off"
    assert client.put(list_url, json=body).json() == first.json()
    assert "set-cookie" not in first.headers
    conflict = client.put(list_url, json={**body, "op_id": new_id()})
    assert conflict.status_code == 409
    reset = client.put(
        list_url, json={"op_id": new_id(), "base_revision": 1, "state": "inherit"}
    )
    assert reset.status_code == 200
    assert client.get(item_url).json()["effective"]["scope"] == "room"
    assert (
        db.execute("SELECT change_seq FROM rooms WHERE id = ?", (room,)).fetchone()[0]
        == before_seq
    )


def test_target_authorization_precedes_retry_and_rule_validation(policy_home):
    _, _, list_id, item_id, _, client, slug = policy_home
    base = f"/api/v1/rooms/{slug}/reminders"
    body = {
        "op_id": new_id(),
        "base_revision": 0,
        "state": "replace",
        "preset": "custom",
        "rules": [{"kind": "relative", "amount": 1, "unit": []}],
    }
    assert client.put(f"{base}/items/{item_id}/policy", json=body).status_code == 422
    valid = {**body, "rules": []}
    assert client.put(f"{base}/lists/{list_id}/policy", json=valid).status_code == 200
    assert client.put(f"{base}/items/999999999/policy", json=valid).status_code == 404
    assert client.put(f"{base}/items/{item_id}/policy", json=valid).status_code == 409


def test_missing_device_cannot_read_or_write_policy(room):
    _, slug, client = room
    url = f"/api/v1/rooms/{slug}/reminders/policy"
    assert client.get(url).status_code == 403
    assert (
        client.put(
            url,
            json={
                "op_id": new_id(),
                "base_revision": 0,
                "state": "replace",
                "preset": "quiet",
            },
        ).status_code
        == 403
    )


def test_http_fixed_identity_is_private_to_policy_and_draft_does_not_resume(
    policy_home,
):
    installation, room_id, list_id, item_id, _, client, slug = policy_home
    base = f"/api/v1/rooms/{slug}/reminders"
    item_url = f"{base}/items/{item_id}/policy"
    list_url = f"{base}/lists/{list_id}/policy"
    wall = {"kind": "fixed", "date": "2030-01-01", "time": "12:00", "timezone": "UTC"}
    body = {
        "op_id": new_id(),
        "base_revision": 0,
        "state": "replace",
        "preset": "custom",
        "rules": [wall],
    }
    first = client.put(item_url, json=body)
    assert first.status_code == 200, first.text
    fixed = first.json()["policy"]["rules"][0]
    other = {**body, "op_id": new_id(), "rules": [{**wall, "id": fixed["id"]}]}
    assert client.put(list_url, json=other).status_code == 422
    with transaction(write=True):
        identity.update_enrollment_locked(installation, room_id, {"status": "revoked"})
    unchanged = {**other, "base_revision": 1}
    response = client.put(item_url, json=unchanged)
    assert response.status_code == 200, response.text
    assert response.json()["policy"]["rules"][0] == fixed
    assert response.json()["policy"]["revision"] == 1
    with transaction():
        assert (
            identity.saved_grant_state_locked(installation, room_id) == "needs_resume"
        )


def test_http_policy_action_reuse_does_not_collide_with_preferences(policy_home):
    _, _, _, _, _, client, slug = policy_home
    base = f"/api/v1/rooms/{slug}/reminders"
    op_id = new_id()
    response = client.put(
        f"{base}/policy",
        json={
            "op_id": op_id,
            "base_revision": 0,
            "state": "replace",
            "preset": "quiet",
        },
    )
    assert response.status_code == 200
    response = client.patch(
        f"{base}/preferences",
        json={"op_id": op_id, "base_revision": 2, "mode": "scheduled"},
    )
    assert response.status_code == 409
    assert client.get(f"{base}/preferences").json()["enrollment"]["mode"] == "quiet"


def test_policy_constraints_and_item_cascade(policy_home):
    import sqlite3

    installation, room_id, _, item_id, clock, _, _ = policy_home
    put(
        policy_home,
        "item",
        preset="custom",
        inputs=[{"kind": "relative", "amount": 1, "unit": "days"}],
    )
    with transaction():
        policy_id = policies.policy_locked(installation, room_id, "item", item_id).id
        assert (
            db.execute(
                "SELECT count(*) FROM reminder_policy_rules WHERE policy_id = ?",
                (policy_id,),
            ).fetchone()[0]
            == 1
        )
    with pytest.raises(sqlite3.IntegrityError), transaction(write=True):
        db.execute(
            "INSERT INTO reminder_policies (installation_id, room_id, scope, item_id, state, preset, summary_enabled, revision, activated_at) VALUES (?, ?, 'item', 999999999, 'replace', 'quiet', 0, 1, ?)",
            (installation, room_id, clock[0].isoformat()),
        )
    with transaction(write=True):
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
    assert (
        db.execute(
            "SELECT count(*) FROM reminder_policies WHERE id = ?", (policy_id,)
        ).fetchone()[0]
        == 0
    )
    assert (
        db.execute(
            "SELECT count(*) FROM reminder_policy_rules WHERE policy_id = ?",
            (policy_id,),
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("scope", ["room", "list", "item"])
@pytest.mark.parametrize("mixed", [False, True], ids=["relative", "mixed"])
def test_http_rule_reordering_preserves_activation_and_catchup(
    policy_home, scope, mixed
):
    _, _, list_id, item_id, clock, client, slug = policy_home
    suffix = {
        "room": "policy",
        "list": f"lists/{list_id}/policy",
        "item": f"items/{item_id}/policy",
    }[scope]
    url = f"/api/v1/rooms/{slug}/reminders/{suffix}"
    relative = {"kind": "relative", "amount": 1, "unit": "days"}
    other = (
        {"kind": "fixed", "date": "2030-01-01", "time": "12:00", "timezone": "UTC"}
        if mixed
        else {"kind": "relative", "amount": 2, "unit": "hours"}
    )
    body = {
        "op_id": new_id(),
        "base_revision": 0,
        "state": "replace",
        "preset": "custom",
        "rules": [relative, other],
    }
    first = client.put(url, json=body)
    assert first.status_code == 200, first.text
    initial = first.json()["policy"]
    before = effective(policy_home)
    fire_at = clock[0] + timedelta(minutes=5)
    clock[0] += timedelta(hours=1)
    reordered = {
        **body,
        "op_id": new_id(),
        "base_revision": initial["revision"],
        "rules": [other, relative],
    }
    result = client.put(url, json=reordered)
    assert result.status_code == 200, result.text
    assert result.json()["policy"] == initial
    after = effective(policy_home)
    assert after.rules == before.rules
    assert after.relative_activations == before.relative_activations
    assert after.summary_activations == before.summary_activations
    assert after.relative_cutoff == before.relative_cutoff
    assert relative_rule_is_active(fire_at, [after.relative_cutoff])
    assert client.put(url, json=reordered).json() == result.json()
    changed = {
        **reordered,
        "op_id": new_id(),
        "rules": [{**relative, "amount": 2}, other],
    }
    updated = client.put(url, json=changed)
    assert updated.status_code == 200, updated.text
    assert updated.json()["policy"]["revision"] == initial["revision"] + 1
    assert effective(policy_home).relative_cutoff == clock[0]
    assert not relative_rule_is_active(
        fire_at, [effective(policy_home).relative_cutoff]
    )
    assert client.put(url, json=reordered).json() == result.json()
    assert client.put(url, json={**reordered, "op_id": new_id()}).status_code == 409


@pytest.mark.parametrize(
    "change", ["fixed_intent", "preset", "summary", "summary_time"]
)
def test_actual_schedule_changes_still_advance_cutoff(policy_home, change):
    clock = policy_home[4]
    fixed = {"kind": "fixed", "date": "2030-01-01", "time": "12:00", "timezone": "UTC"}
    original = put(policy_home, preset="custom", inputs=[fixed])
    clock[0] += timedelta(hours=1)
    if change == "fixed_intent":
        changed = put(
            policy_home,
            preset="custom",
            inputs=[{**fixed, "time": "13:00", "id": original.rules[0].id}],
        )
        assert changed.rules[0].id != original.rules[0].id
    elif change == "preset":
        changed = put(policy_home, preset="scheduled")
    elif change == "summary":
        changed = put(policy_home, preset="custom", inputs=[fixed], summary=True)
    else:
        changed = put(
            policy_home, preset="custom", inputs=[fixed], summary_time="10:30"
        )
    assert changed.revision == original.revision + 1
    assert effective(policy_home).relative_cutoff == clock[0]


def test_cross_room_targets_and_forged_cookie_denied_before_retry(policy_home):
    from api_helpers import client_for

    _, room_id, list_id, _, _, client, slug = policy_home
    password_hash = db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]
    other_room = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES ('Other', 'other-private', ?)",
        (password_hash,),
    ).lastrowid
    other_list = db.execute(
        "INSERT INTO lists (name, slug, room_id, share_token) VALUES ('Other', 'other-list', ?, 'other-share')",
        (other_room,),
    ).lastrowid
    other_item = db.execute(
        "INSERT INTO items (name, name_key, done, list_id) VALUES ('Other', 'other', 0, ?)",
        (other_list,),
    ).lastrowid
    db.commit()
    root = f"/api/v1/rooms/{slug}/reminders"
    body = {"op_id": new_id(), "base_revision": 0, "state": "off"}
    first = client.put(f"{root}/lists/{list_id}/policy", json=body)
    assert first.status_code == 200, first.text
    before = db.execute("SELECT id, change_seq FROM rooms ORDER BY id").fetchall()
    count = db.execute("SELECT count(*) FROM reminder_processed_ops").fetchone()[0]
    for target in (f"lists/{other_list}/policy", f"items/{other_item}/policy"):
        for response in (
            client.get(f"{root}/{target}"),
            client.put(f"{root}/{target}", json=body),
        ):
            assert response.status_code == 404
            assert "policy" not in response.json()
            assert "set-cookie" not in response.headers
    assert (
        client.post(f"{root}/preview", json={"item_id": other_item}).status_code == 404
    )
    forged = client_for(slug)
    forged.cookies.set(
        "__Host-listapp-device", "forged-secret", domain="testserver.local", path="/"
    )
    for response in (
        forged.get(f"{root}/lists/{list_id}/policy"),
        forged.put(f"{root}/lists/{list_id}/policy", json=body),
        forged.post(f"{root}/preview", json={"item_id": other_item}),
    ):
        assert response.status_code == 403
        assert (
            "__Host-listapp-device=forged-secret" in response.request.headers["cookie"]
        )
        assert response.json()["error"]["code"] == "not_enrolled"
        assert "policy" not in response.json()
        assert "set-cookie" not in response.headers
    assert (
        db.execute("SELECT id, change_seq FROM rooms ORDER BY id").fetchall() == before
    )
    assert (
        db.execute("SELECT count(*) FROM reminder_processed_ops").fetchone()[0] == count
    )


def test_preview_draft_is_private_and_read_only(policy_home):
    home = policy_home
    _installation, room, _list, item, _clock, client, slug = home
    before = (
        db.execute("SELECT * FROM reminder_installations").fetchall(),
        db.execute("SELECT * FROM reminder_enrollments").fetchall(),
        db.execute("SELECT * FROM reminder_processed_ops").fetchall(),
        db.execute("SELECT * FROM reminder_policies").fetchall(),
        db.execute("SELECT * FROM items").fetchall(),
        db.execute("SELECT change_seq FROM rooms WHERE id = ?", (room,)).fetchone(),
    )
    url = f"/api/v1/rooms/{slug}/reminders/preview"
    body = {
        "item_id": item,
        "draft": {
            "state": "replace",
            "preset": "custom",
            "rules": [{"kind": "relative", "amount": 0, "unit": "days"}],
        },
    }
    response = client.post(url, json=body)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers
    assert response.json()["entries"][0]["keys"] == ["at-due"]
    assert client.post(url, json={**body, "due_at": "forged"}).status_code == 422
    assert client.post(url, json={"item_id": item + 999999}).status_code == 404
    after = (
        db.execute("SELECT * FROM reminder_installations").fetchall(),
        db.execute("SELECT * FROM reminder_enrollments").fetchall(),
        db.execute("SELECT * FROM reminder_processed_ops").fetchall(),
        db.execute("SELECT * FROM reminder_policies").fetchall(),
        db.execute("SELECT * FROM items").fetchall(),
        db.execute("SELECT change_seq FROM rooms WHERE id = ?", (room,)).fetchone(),
    )
    assert before == after


def test_preview_each_installation_uses_its_own_policy(policy_home):
    from api_helpers import client_for

    _, _, _, item, _, first, slug = policy_home
    second = client_for(slug)
    enrolled = second.post(
        f"/api/v1/rooms/{slug}/reminders/enrollment",
        json={"op_id": new_id(), "timezone": "Europe/Oslo", "mode": "quiet"},
    )
    assert enrolled.status_code == 200
    path = f"/api/v1/rooms/{slug}/reminders/preview"
    a = first.post(path, json={"item_id": item})
    b = second.post(path, json={"item_id": item})
    assert a.status_code == b.status_code == 200
    assert a.json()["entries"]
    assert b.json()["entries"] == []
    assert b.json()["disabled_reasons"] == ["policy_off"]


def test_share_only_cannot_preview_personal_policies(policy_home):
    from api_helpers import client_for, rotate_list_share_token

    _, _, list_id, item, _, _, slug = policy_home
    token = rotate_list_share_token(list_id)
    visitor = client_for()
    assert not visitor.cookies
    share = visitor.get(f"/api/v1/share/{token}/changes?since=0")
    assert share.status_code == 200
    assert share.json()["room"] is None
    assert not visitor.cookies
    response = visitor.post(
        f"/api/v1/rooms/{slug}/reminders/preview", json={"item_id": item}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert "set-cookie" not in response.headers
    assert not visitor.cookies


def test_public_uid_targets_preserve_ownership_and_retry(policy_home):
    from api_helpers import client_for, rotate_list_share_token

    _, room_id, list_id, item_id, _, client, slug = policy_home
    list_uid, item_uid = new_id(), new_id()
    db.execute("UPDATE lists SET uid = ? WHERE id = ?", (list_uid, list_id))
    db.execute("UPDATE items SET uid = ? WHERE id = ?", (item_uid, item_id))
    password = db.execute(
        "SELECT password_hash FROM rooms WHERE id = ?", (room_id,)
    ).fetchone()[0]
    other_room = db.execute(
        "INSERT INTO rooms (name, slug, password_hash) VALUES ('Other', 'uid-other', ?)",
        (password,),
    ).lastrowid
    other_uid, other_item_uid = new_id(), new_id()
    other_list = db.execute(
        "INSERT INTO lists (name, slug, room_id, uid, share_token) VALUES ('Other', 'uid-other-list', ?, ?, 'uid-other-share')",
        (other_room, other_uid),
    ).lastrowid
    db.execute(
        "INSERT INTO items (name, name_key, done, list_id, uid) VALUES ('Other', 'other', 0, ?, ?)",
        (other_list, other_item_uid),
    )
    db.commit()
    root = f"/api/v1/rooms/{slug}/reminders"
    body = {"op_id": new_id(), "base_revision": 0, "state": "off"}
    url = f"{root}/lists/{list_uid}/policy"
    first = client.put(url, json=body)
    assert first.status_code == 200
    assert client.put(url, json=body).json() == first.json()
    assert client.put(f"{root}/items/{item_uid}/policy", json=body).status_code == 409
    for kind, uid in (("lists", other_uid), ("items", other_item_uid)):
        assert client.get(f"{root}/{kind}/{uid}/policy").status_code == 404
        assert client.put(f"{root}/{kind}/{uid}/policy", json=body).status_code == 404
    assert client.get(f"{root}/items/not-a-uuid/policy").status_code == 404
    assert client.get(f"{root}/items/{'9' * 100}/policy").status_code == 404
    assert client.get(f"{root}/items/{item_uid}/policy").status_code == 200
    before = db.execute("SELECT count(*) FROM reminder_processed_ops").fetchone()[0]
    preview = client.post(f"{root}/preview", json={"item_uid": item_uid})
    assert preview.status_code == 200 and "set-cookie" not in preview.headers
    assert (
        client.post(f"{root}/preview", json={"item_uid": other_item_uid}).status_code
        == 404
    )
    assert (
        client.post(
            f"{root}/preview", json={"item_uid": item_uid, "item_id": item_id}
        ).status_code
        == 422
    )
    assert (
        db.execute("SELECT count(*) FROM reminder_processed_ops").fetchone()[0]
        == before
    )
    forged = client_for(slug)
    forged.cookies.set(
        "__Host-listapp-device", "forged", domain="testserver.local", path="/"
    )
    assert forged.get(f"{root}/items/{item_uid}/policy").status_code == 403
    assert (
        forged.post(f"{root}/preview", json={"item_uid": other_item_uid}).status_code
        == 403
    )
    visitor = client_for()
    token = rotate_list_share_token(list_id)
    assert visitor.get(f"/api/v1/share/{token}/changes?since=0").status_code == 200
    assert visitor.get(f"{root}/lists/{list_uid}/policy").status_code == 401
    assert (
        visitor.post(f"{root}/preview", json={"item_uid": item_uid}).status_code == 401
    )
