"""Shared timed dates survive offline conflict and undo without inventing UTC."""

import re

from playwright.sync_api import expect
from svelte_app import sign_in, wait_until
from test_svelte_offline_reconnect import (
    NO_WORKER,
    SLOW,
    go_online,
    member_with_list,
    view_offline,
)


def open_item(page):
    page.get_by_role("button", name=re.compile("^milk")).click()
    return page.get_by_role("dialog", name="Edit Item")


def set_due(dialog, day, time, zone):
    dialog.get_by_label("Date").fill(day)
    dialog.get_by_label("Due time (optional)").fill(time)
    dialog.get_by_label(re.compile("Time zone")).fill(zone)
    dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_have_count(0)


def test_timed_edit_conflict_save_mine_retries_and_reconfirms(
    svelte_server, open_session
):
    server = svelte_server
    phone, url = member_with_list(open_session, server, "timed-conflict")
    set_due(open_item(phone), "2026-10-18", "09:00", "Europe/Oslo")
    wait_until(
        phone,
        lambda: bool(server.query("SELECT due_at FROM items WHERE name='milk'")[0][0]),
        "initial due missing",
    )
    view_offline(phone, url)
    set_due(open_item(phone), "2026-10-19", "10:30", "Asia/Kathmandu")
    dialog = open_item(phone)
    expect(dialog.get_by_text(re.compile("Waiting to sync"))).to_be_visible()
    expect(dialog.get_by_text(re.compile("Server-confirmed UTC"))).to_have_count(0)
    dialog.get_by_role("button", name="Cancel").click()
    other = open_session("timed-other", **NO_WORKER)
    sign_in(other, server)
    other.goto(url)
    dialog = open_item(other)
    dialog.get_by_label("Description / Notes").fill("other device")
    dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_have_count(0)
    wait_until(
        other,
        lambda: (
            server.query("SELECT description FROM items WHERE name='milk'")
            == [("other device",)]
        ),
        "other edit missing",
    )
    go_online(phone)
    expect(phone.get_by_text("1 change was not saved")).to_be_visible(**SLOW)
    phone.get_by_role("button", name="Review").click()
    phone.get_by_role("dialog").get_by_role(
        "button", name="Save mine anyway", exact=True
    ).click()
    wait_until(
        phone,
        lambda: (
            server.query(
                "SELECT date, due_time, due_timezone FROM items WHERE name='milk'"
            )
            == [("2026-10-19", "10:30", "Asia/Kathmandu")]
        ),
        "retry missing",
        timeout_ms=20000,
    )
    expect(phone.get_by_role("img", name="Not sent yet")).to_have_count(
        0, timeout=20000
    )
    dialog = open_item(phone)
    expect(dialog.get_by_text(re.compile("Server-confirmed UTC"))).to_be_visible(**SLOW)


def test_timed_delete_undo_offline_reconfirms(svelte_server, open_session):
    server = svelte_server
    phone, url = member_with_list(open_session, server, "timed-undo")
    set_due(open_item(phone), "2026-10-18", "09:00", "Europe/Oslo")
    wait_until(
        phone,
        lambda: bool(server.query("SELECT due_at FROM items WHERE name='milk'")[0][0]),
        "initial due missing",
    )
    original_uid = server.query("SELECT uid FROM items WHERE name='milk'")[0][0]
    view_offline(phone, url)
    open_item(phone).get_by_role("button", name="Delete Item").click()
    phone.get_by_role("button", name="Undo").click()
    dialog = open_item(phone)
    expect(dialog.get_by_label("Due time (optional)")).to_have_value("09:00")
    expect(dialog.get_by_label(re.compile("Time zone"))).to_have_value("Europe/Oslo")
    expect(dialog.get_by_text(re.compile("Waiting to sync"))).to_be_visible()
    dialog.get_by_role("button", name="Cancel").click()
    go_online(phone)
    wait_until(
        phone,
        lambda: (
            server.query(
                "SELECT uid, date, due_time, due_timezone FROM items WHERE name='milk'"
            )
            and server.query("SELECT uid FROM items WHERE name='milk'")[0][0]
            != original_uid
        ),
        "restore missing",
        timeout_ms=20000,
    )
    expect(phone.get_by_role("img", name="Not sent yet")).to_have_count(
        0, timeout=20000
    )
    assert server.query(
        "SELECT date, due_time, due_timezone FROM items WHERE name='milk'"
    ) == [("2026-10-18", "09:00", "Europe/Oslo")]
    assert server.query("SELECT due_at FROM items WHERE name='milk'")[0][0]
    dialog = open_item(phone)
    expect(dialog.get_by_text(re.compile("Server-confirmed UTC"))).to_be_visible(**SLOW)
