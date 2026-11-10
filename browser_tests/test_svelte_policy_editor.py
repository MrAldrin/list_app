"""The private policy editor uses room-owned public identifiers and direct writes."""

import re
from datetime import date, timedelta

import pytest
from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, sign_in
from test_svelte_due_center import _set_date
from test_svelte_private_reminders import open_settings

# Paused until S3, so these run on Chromium only. When S3 enables them, choose
# engines by the rule in docs/browser-testing.md (lr-347.9.2).
pytestmark = pytest.mark.skip(
    reason="P2: re-enable in S3 (plans/batches/reminders-s3.md#deferred-polish-from-p2)"
)


def test_policy_inheritance_preview_and_retry(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    settings = open_settings(page)
    settings.get_by_role("button", name="Enroll this device").click()
    expect(settings.get_by_text("Status: Active")).to_be_visible()
    settings.get_by_role("button", name="Close").click()
    create_list(page, "Groceries")
    add_item(page, "milk")
    _set_date(page, "milk", (date.today() + timedelta(days=10)).isoformat())
    page.get_by_role("button", name=re.compile("^Due items:")).click()
    panel = page.get_by_role("dialog", name="Due items")
    panel.get_by_role("button", name="List reminder policy").click()
    editor = page.get_by_role("dialog", name="Personal list reminders")
    expect(editor.get_by_text("Effective source: room", exact=False)).to_be_visible()
    editor.get_by_label("Policy").select_option("off")
    editor.get_by_role("button", name="Save policy").click()
    expect(editor.get_by_text("Saved on this device.")).to_be_visible()
    editor.get_by_label("Policy").select_option("inherit")
    editor.get_by_role("button", name="Save policy").click()
    expect(editor.get_by_text("Effective source: room", exact=False)).to_be_visible()
    editor.get_by_role("button", name="Close").click()
    panel.get_by_role("button", name="Private reminder settings for milk").click()
    editor = page.get_by_role("dialog", name="Personal item reminders")
    editor.get_by_label("Policy").select_option("replace")
    editor.get_by_label("Schedule").select_option("custom")
    editor.get_by_role("button", name="Add relative rule").click()
    editor.get_by_role("button", name="Preview next five").click()
    expect(editor.get_by_role("heading", name="Preview: item policy")).to_be_visible()
    bodies = []

    def lose_first(route):
        if route.request.method != "PUT":
            route.continue_()
            return
        bodies.append(route.request.post_data)
        if len(bodies) == 1:
            assert route.fetch().status == 200
            route.abort()
        else:
            route.continue_()

    page.route("**/reminders/items/*/policy", lose_first)
    editor.get_by_role("button", name="Save policy").click()
    expect(editor.get_by_role("button", name="Retry request")).to_be_visible()
    editor.get_by_role("button", name="Retry request").click()
    expect(editor.get_by_text("Saved on this device.")).to_be_visible()
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    page.context.set_offline(True)
    expect(editor.get_by_role("button", name="Save policy")).to_be_disabled()
    expect(editor.get_by_label("Amount before due")).to_have_value("1")
    page.context.set_offline(False)


def test_fixed_identity_and_explicit_conflict_recovery(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    settings = open_settings(page)
    settings.get_by_role("button", name="Enroll this device").click()
    expect(settings.get_by_text("Status: Active")).to_be_visible()
    settings.get_by_role("button", name="Close").click()
    create_list(page, "Groceries")
    add_item(page, "milk")
    _set_date(page, "milk", (date.today() + timedelta(days=10)).isoformat())
    page.get_by_role("button", name=re.compile("^Due items:")).click()
    page.get_by_role("dialog", name="Due items").get_by_role(
        "button", name="Private reminder settings for milk"
    ).click()
    editor = page.get_by_role("dialog", name="Personal item reminders")
    editor.get_by_label("Policy").select_option("replace")
    editor.get_by_label("Schedule").select_option("custom")
    editor.get_by_role("button", name="Add fixed wall time").click()
    editor.get_by_label("Wall date").fill(
        (date.today() + timedelta(days=800)).isoformat()
    )
    expect(editor.get_by_label("Wall time")).to_have_attribute("inputmode", "text")
    editor.get_by_label("Wall time").fill("12:00")
    editor.get_by_label("Time zone").fill("UTC")
    with page.expect_response(
        lambda r: "/reminders/items/" in r.url and r.request.method == "PUT"
    ) as response:
        editor.get_by_role("button", name="Save policy").click()
    first = response.value.json()["policy"]
    original = first["rules"][0]
    expect(editor.get_by_text("Confirmed UTC:", exact=False)).to_be_visible()
    with page.expect_response(
        lambda r: "/reminders/items/" in r.url and r.request.method == "PUT"
    ) as response:
        editor.get_by_role("button", name="Save policy").click()
    assert response.value.json()["policy"]["rules"][0]["id"] == original["id"]
    editor.get_by_label("Wall time").fill("13:00")
    with page.expect_response(
        lambda r: "/reminders/items/" in r.url and r.request.method == "PUT"
    ) as response:
        editor.get_by_role("button", name="Save policy").click()
    changed = response.value.json()["policy"]
    assert changed["rules"][0]["id"] != original["id"]
    url = response.value.url
    external = page.request.put(
        url,
        headers={"Origin": page.evaluate("location.origin")},
        data={
            "op_id": "d8c615e2-0b61-4739-b125-8312dcc0113e",
            "base_revision": changed["revision"],
            "state": "off",
        },
    )
    assert external.status == 200
    editor.get_by_label("Wall time").fill("14:00")
    editor.get_by_role("button", name="Save policy").click()
    expect(editor.get_by_role("button", name="Load latest revision")).to_be_visible()
    editor.get_by_role("button", name="Load latest revision").click()
    expect(editor.get_by_label("Wall time")).to_have_value("14:00")


def test_device_zone_updates_due_views_without_reload(svelte_server, open_session):
    page = open_session("owner", **PHONE, timezone_id="UTC")
    page.clock.install(time="2035-01-01T23:30:00Z")
    sign_in(page, svelte_server)
    settings = open_settings(page)
    settings.get_by_text("Change time zone", exact=True).click()
    settings.get_by_label("Time zone for this device").fill("UTC")
    settings.get_by_role("button", name="Enroll this device").click()
    expect(settings.get_by_text("Status: Active")).to_be_visible()
    settings.get_by_role("button", name="Close").click()
    create_list(page, "Groceries")
    add_item(page, "milk")
    _set_date(page, "milk", "2035-01-02")
    expect(page.locator(".row", has_text="milk")).to_contain_text("Tomorrow")
    page.goto(page.url.split("/list/")[0])
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Personal reminders").click()
    settings = page.get_by_role("dialog", name="Personal reminders")
    expect(settings.get_by_text("Status: Active")).to_be_visible()
    settings.get_by_text("Change device time zone", exact=True).click()
    settings.get_by_label("Device time zone").fill("Pacific/Kiritimati")
    settings.get_by_label("Confirm time zone change", exact=False).check()
    settings.get_by_role("button", name="Save device settings").click()
    expect(settings.get_by_text("Saved on this device.")).to_be_visible()
    settings.get_by_role("button", name="Close").click()
    page.get_by_role("button", name=re.compile("^Due items:")).click()
    expect(
        page.get_by_role("dialog", name="Due items").get_by_role(
            "heading", name=re.compile("^Today")
        )
    ).to_be_visible()
    page.get_by_role("dialog", name="Due items").get_by_role(
        "link", name=re.compile("^milk")
    ).click()
    expect(page.locator(".row", has_text="milk")).to_contain_text("Today")


def test_two_installations_and_share_link_do_not_leak_policy(
    svelte_server, open_session
):
    from svelte_app import share_link

    owner = open_session("owner", **PHONE)
    sign_in(owner, svelte_server)
    settings = open_settings(owner)
    settings.get_by_role("button", name="Enroll this device").click()
    expect(settings.get_by_text("Status: Active")).to_be_visible()
    settings.get_by_role("button", name="Close").click()
    create_list(owner, "Groceries")
    add_item(owner, "milk")
    _set_date(owner, "milk", (date.today() + timedelta(days=10)).isoformat())
    link = share_link(owner)
    room_url = owner.url.split("/list/")[0]
    owner.get_by_role("button", name=re.compile("^Due items:")).click()
    owner.get_by_role("dialog", name="Due items").get_by_role(
        "button", name="List reminder policy"
    ).click()
    editor = owner.get_by_role("dialog", name="Personal list reminders")
    editor.get_by_label("Policy").select_option("off")
    editor.get_by_role("button", name="Save policy").click()
    expect(editor.get_by_text("Saved on this device.")).to_be_visible()

    guest = open_session("guest", **PHONE)
    guest.goto(link)
    expect(guest.get_by_role("heading", name="Groceries")).to_be_visible()
    guest.get_by_role("button", name=re.compile("^Due items:")).click()
    expect(
        guest.get_by_role("button", name=re.compile("reminder policy", re.I))
    ).to_have_count(0)
    assert not any("device" in cookie["name"] for cookie in guest.context.cookies())

    second = open_session("second", **PHONE)
    sign_in(second, svelte_server)
    second.goto(room_url)
    settings2 = open_settings(second)
    settings2.get_by_role("button", name="Enroll this device").click()
    expect(settings2.get_by_text("Status: Active")).to_be_visible()
    settings2.get_by_role("button", name="Close").click()
    second.get_by_role("link", name="Groceries").click()
    second.get_by_role("button", name=re.compile("^Due items:")).click()
    second.get_by_role("dialog", name="Due items").get_by_role(
        "button", name="List reminder policy"
    ).click()
    second_editor = second.get_by_role("dialog", name="Personal list reminders")
    expect(second_editor.get_by_label("Policy")).to_have_value("inherit")
    expect(
        second_editor.get_by_text("Effective source: room", exact=False)
    ).to_be_visible()


def test_room_policy_and_enrollment_mode_stay_in_sync(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Personal room reminder policy").click()
    editor = page.get_by_role("dialog", name="Personal room reminders")
    editor.get_by_role("button", name="Open enrollment settings").click()
    settings = page.get_by_role("dialog", name="Personal reminders")
    expect(settings.get_by_text("Status: Not enrolled")).to_be_visible()
    settings.get_by_role("button", name="Enroll this device").click()
    expect(settings.get_by_text("Status: Active")).to_be_visible()
    settings.get_by_role("button", name="Close").click()
    editor.get_by_label("Schedule").select_option("scheduled")
    editor.get_by_role("button", name="Save policy").click()
    expect(editor.get_by_text("Saved on this device.")).to_be_visible()
    editor.get_by_role("button", name="Close").click()
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Personal reminders", exact=True).click()
    settings = page.get_by_role("dialog", name="Personal reminders")
    expect(settings.get_by_label("Room reminder mode")).to_have_value("scheduled")


def test_preview_renders_rule_and_summary_at_same_instant(svelte_server, open_session):
    page = open_session("owner", **PHONE, timezone_id="UTC")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    sign_in(page, svelte_server)
    settings = open_settings(page)
    settings.get_by_text("Change time zone", exact=True).click()
    settings.get_by_label("Time zone for this device").fill("UTC")
    settings.get_by_role("button", name="Enroll this device").click()
    expect(settings.get_by_text("Status: Active")).to_be_visible()
    settings.get_by_role("button", name="Close").click()
    create_list(page, "Groceries")
    add_item(page, "milk")
    page.get_by_role("button", name=re.compile("^milk")).click()
    item = page.get_by_role("dialog", name="Edit Item")
    item.get_by_label("Date", exact=True).fill(
        (date.today() + timedelta(days=10)).isoformat()
    )
    item.get_by_label("Due time (optional)").fill("09:00")
    item.get_by_text("Change time zone", exact=True).click()
    item.get_by_label("Time zone", exact=False).fill("UTC")
    item.get_by_role("button", name="Save", exact=True).click()
    expect(item).to_be_hidden()
    page.get_by_role("button", name=re.compile("^Due items:")).click()
    page.get_by_role("dialog", name="Due items").get_by_role(
        "button", name="Private reminder settings for milk"
    ).click()
    editor = page.get_by_role("dialog", name="Personal item reminders")
    editor.get_by_label("Policy").select_option("replace")
    editor.get_by_label("Schedule").select_option("custom")
    editor.get_by_label("Include daily summary").check()
    editor.get_by_role("button", name="Add relative rule").click()
    editor.get_by_label("Amount before due").fill("0")
    with page.expect_response(
        lambda r: r.url.endswith("/reminders/preview") and r.request.method == "POST"
    ) as response:
        editor.get_by_role("button", name="Preview next five").click()
    entries = response.value.json()["entries"]
    collision = next(e["instant"] for e in entries if e["kind"] == "rules")
    assert any(e["kind"] == "summary" and e["instant"] == collision for e in entries)
    expect(
        editor.locator("li", has_text=f"rules: original UTC {collision}")
    ).to_be_visible()
    expect(
        editor.locator("li", has_text=f"summary: original UTC {collision}")
    ).to_be_visible()
    editor.get_by_label("Amount before due").fill("1")
    editor.get_by_role("button", name="Preview next five").click()
    expect(editor.get_by_role("heading", name="Preview: item policy")).to_be_visible()
    expect(editor.locator("li", has_text="rules: original UTC")).to_be_visible()
    assert not errors
