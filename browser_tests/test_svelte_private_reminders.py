"""Private settings require an explicit enrollment and stay out of the shared queue."""

import json
import sqlite3

import pytest
from playwright.sync_api import expect
from svelte_app import PHONE, app_url, create_list, share_link, sign_in
from test_svelte_room_switcher import CABIN_PASSWORD, create_room_as_admin
from test_svelte_share import without_share_sheet


def open_settings(page):
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Personal reminders").click()
    dialog = page.get_by_role("dialog", name="Personal reminders")
    expect(dialog.get_by_text("Status: Not enrolled")).to_be_visible()
    return dialog


def test_enrollment_settings_and_offline_draft(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    requests = []
    page.on(
        "request",
        lambda r: (
            requests.append((r.method, r.url)) if "/reminders/" in r.url else None
        ),
    )
    dialog = open_settings(page)
    assert all(method == "GET" for method, _ in requests)
    assert not any("device" in c["name"] for c in page.context.cookies())
    expect(
        dialog.get_by_text("Reminder delivery is not active", exact=False)
    ).to_be_visible()
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    assert any("device" in c["name"] for c in page.context.cookies())
    dialog.get_by_label("Room reminder mode").select_option("quiet")
    dialog.get_by_role("button", name="Save room settings").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    dialog.get_by_label("Room reminder mode").select_option("daily_summary")
    dialog.get_by_label("All-day reminder time").fill("10:15")
    dialog.get_by_role("button", name="Save device settings").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    dialog.get_by_label("Room summary time").fill("11:45")
    before = len(requests)
    page.context.set_offline(True)
    expect(dialog.get_by_role("button", name="Save room settings")).to_be_disabled()
    expect(dialog.get_by_label("Room summary time")).to_have_value("11:45")
    queued = page.evaluate("""async () => {
        const db = await new Promise((resolve, reject) => {
            const request = indexedDB.open('listr-queue');
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
        const rows = await new Promise((resolve, reject) => {
            const request = db.transaction('queue').objectStore('queue').getAll();
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
        db.close();
        return JSON.stringify(rows);
    }""")
    assert "11:45" not in queued
    assert len(requests) == before
    page.context.set_offline(False)
    expect(dialog.get_by_role("button", name="Save room settings")).to_be_enabled()
    expect(dialog.get_by_label("Room summary time")).to_have_value("11:45")


def test_lost_response_retries_same_operation(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    bodies = []

    def lose_first_response(route):
        bodies.append(route.request.post_data)
        if len(bodies) == 1:
            response = route.fetch()
            assert response.status == 200
            route.abort()
        else:
            route.continue_()

    page.route("**/reminders/preferences", lose_first_response)
    dialog.get_by_label("Room reminder mode").select_option("quiet")
    dialog.get_by_role("button", name="Save room settings").click()
    expect(dialog.get_by_role("button", name="Retry request")).to_be_visible()
    dialog.get_by_role("button", name="Retry request").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    page.unroute("**/reminders/preferences", lose_first_response)


@pytest.mark.parametrize(
    "action,malformed",
    [
        ("room", "{"),
        ("room", "{}"),
        ("enroll", "{"),
        ("optout", "{}"),
        ("device", "{}"),
    ],
)
def test_unusable_success_retries_committed_operation(
    svelte_server, open_session, action, malformed
):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    if action != "enroll":
        dialog.get_by_role("button", name="Enroll this device").click()
        expect(dialog.get_by_text("Status: Active")).to_be_visible()
    bodies = []
    endpoint = (
        "enrollment"
        if action == "enroll"
        else "preferences/device"
        if action == "device"
        else "preferences"
    )
    expected_method = "POST" if action == "enroll" else "PATCH"

    def corrupt_first(route):
        if route.request.method != expected_method:
            route.continue_()
            return
        bodies.append(route.request.post_data)
        if len(bodies) == 1:
            response = route.fetch()
            assert response.status == 200
            route.fulfill(response=response, body=malformed)
        else:
            route.continue_()

    page.route(f"**/reminders/{endpoint}", corrupt_first)
    if action == "room":
        dialog.get_by_label("Room reminder mode").select_option("quiet")
    if action == "device":
        dialog.get_by_label("All-day reminder time").fill("13:25")
    button = {
        "room": "Save room settings",
        "enroll": "Enroll this device",
        "optout": "Opt out of this room",
        "device": "Save device settings",
    }[action]
    dialog.get_by_role("button", name=button).click()
    expect(dialog.get_by_role("button", name="Retry request")).to_be_visible()
    expect(dialog.get_by_label("Room reminder mode")).to_be_disabled()
    dialog.get_by_role("button", name="Retry request").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    op_id = json.loads(bodies[0])["op_id"]
    assert svelte_server.query(
        "SELECT COUNT(*) FROM reminder_processed_ops WHERE op_id = ?", (op_id,)
    ) == [(1,)]
    assert svelte_server.query("SELECT COUNT(*) FROM reminder_installations") == [(1,)]
    page.unroute(f"**/reminders/{endpoint}", corrupt_first)


def test_body_read_failure_after_server_commit(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    bodies = []
    page.on(
        "request",
        lambda r: (
            bodies.append(r.post_data)
            if r.method == "PATCH" and r.url.endswith("/reminders/preferences")
            else None
        ),
    )
    page.evaluate("""() => {
        const real = window.fetch;
        let fail = true;
        window.fetch = async (...args) => {
            const response = await real(...args);
            if (fail && String(args[0]).endsWith('/reminders/preferences') && args[1]?.method === 'PATCH') {
                fail = false;
                Object.defineProperty(response, 'json', {value: async () => {throw new TypeError('body stream failed')}});
            }
            return response;
        };
    }""")
    dialog.get_by_label("Room reminder mode").select_option("quiet")
    dialog.get_by_role("button", name="Save room settings").click()
    expect(dialog.get_by_role("button", name="Retry request")).to_be_visible()
    dialog.get_by_role("button", name="Retry request").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    op_id = json.loads(bodies[0])["op_id"]
    assert svelte_server.query(
        "SELECT COUNT(*) FROM reminder_processed_ops WHERE op_id = ?", (op_id,)
    ) == [(1,)]


@pytest.mark.parametrize("retry", [False, True])
def test_expired_device_identity_preserves_draft_and_requires_enrollment(
    svelte_server, open_session, retry
):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    dialog.get_by_label("Room summary time").fill("11:45")
    if retry:
        attempts = []

        def lose_response(route):
            if route.request.method == "PATCH" and not attempts:
                attempts.append(route.request.post_data)
                response = route.fetch()
                assert response.status == 200
                route.fulfill(response=response, body="{")
            else:
                route.continue_()

        page.route("**/reminders/preferences", lose_response)
        dialog.get_by_role("button", name="Save room settings").click()
        expect(dialog.get_by_role("alert")).to_contain_text("result is unknown")
    page.context.clear_cookies(name="listapp-device")
    dialog.get_by_role(
        "button", name="Retry request" if retry else "Save room settings"
    ).click()
    expect(dialog.get_by_text("Status: Not enrolled")).to_be_visible()
    expect(dialog.get_by_role("alert")).to_contain_text(
        "previous request may have committed"
    )
    expect(dialog.get_by_label("Room summary time")).to_have_value("11:45")
    expect(dialog.get_by_role("button", name="Retry request")).to_have_count(0)
    assert svelte_server.query("SELECT COUNT(*) FROM reminder_installations") == [(1,)]
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    expect(dialog.get_by_label("Room summary time")).to_have_value("11:45")
    assert svelte_server.query("SELECT COUNT(*) FROM reminder_installations") == [(2,)]


def test_revoked_grant_needs_explicit_resume(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    dialog.get_by_role("button", name="Close").click()
    page.get_by_role("button", name="Room menu").click()
    with page.expect_response(
        lambda r: r.request.method == "DELETE" and r.url.endswith("/session")
    ):
        page.get_by_role("button", name="Log out").click()
    expect(page.get_by_label("Room Password")).to_be_visible()
    page.get_by_label("Room Password").fill(svelte_server.password)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("button", name="Add New List")).to_be_visible()
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Personal reminders").click()
    dialog = page.get_by_role("dialog", name="Personal reminders")
    expect(dialog.get_by_text("Status: Needs resume")).to_be_visible()
    expect(dialog.get_by_role("button", name="Resume this room")).to_be_visible()
    dialog.get_by_role("button", name="Resume this room").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()


def test_opt_out_requires_explicit_resume(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    dialog.get_by_role("button", name="Opt out of this room").click()
    expect(dialog.get_by_text("Status: Opted out")).to_be_visible()
    dialog.get_by_role("button", name="Save device settings").click()
    expect(dialog.get_by_text("Status: Opted out")).to_be_visible()
    dialog.get_by_role("button", name="Resume this room").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()


def assert_device_draft(dialog):
    expect(dialog.get_by_label("Device time zone")).to_have_value("Europe/Oslo")
    expect(
        dialog.get_by_label("Confirm time zone change for all enrolled rooms")
    ).to_be_checked()
    expect(dialog.get_by_label("All-day reminder time")).to_have_value("13:25")
    expect(dialog.get_by_label("Pause reminders on this device")).to_be_checked()


def edit_device_draft(dialog):
    # The initial setup in these tests uses UTC.
    dialog.get_by_text("Change device time zone", exact=True).click()
    dialog.get_by_label("Device time zone").fill("Europe/Oslo")
    dialog.get_by_label("Confirm time zone change for all enrolled rooms").check()
    dialog.get_by_label("All-day reminder time").fill("13:25")
    dialog.get_by_label("Pause reminders on this device").check()


def test_optout_resume_preserves_unrelated_drafts(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_text("Change time zone", exact=True).click()
    dialog.get_by_label("Time zone for this device").fill("UTC")
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    dialog.get_by_label("Room reminder mode").select_option("daily_summary")
    dialog.get_by_label("Room summary time").fill("11:45")
    dialog.get_by_role("button", name="Opt out of this room").click()
    expect(dialog.get_by_text("Status: Opted out")).to_be_visible()
    expect(dialog.get_by_label("Room reminder mode")).to_have_value("daily_summary")
    expect(dialog.get_by_label("Room summary time")).to_have_value("11:45")
    edit_device_draft(dialog)
    dialog.get_by_role("button", name="Resume this room").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    assert_device_draft(dialog)


def test_enroll_other_room_preserves_existing_device_draft(svelte_server, open_session):
    admin = open_session("admin", **PHONE)
    slug = create_room_as_admin(admin, svelte_server, "Cabin", CABIN_PASSWORD)
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_text("Change time zone", exact=True).click()
    dialog.get_by_label("Time zone for this device").fill("UTC")
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    dialog.get_by_role("button", name="Close").click()
    page.goto(app_url(svelte_server, f"room/{slug}"))
    page.get_by_label("Room Password").fill(CABIN_PASSWORD)
    page.get_by_label("Room Password").press("Enter")
    expect(page.get_by_role("button", name="Add New List")).to_be_visible()
    dialog = open_settings(page)
    edit_device_draft(dialog)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    assert_device_draft(dialog)


@pytest.mark.parametrize("other_room", [False, True])
@pytest.mark.parametrize("unknown", [False, True])
def test_enrollment_expiry_recovers_only_after_explicit_action(
    svelte_server, open_session, other_room, unknown
):
    if other_room:
        admin = open_session("admin", **PHONE)
        slug = create_room_as_admin(admin, svelte_server, "Cabin", CABIN_PASSWORD)
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_text("Change time zone", exact=True).click()
    dialog.get_by_label("Time zone for this device").fill("UTC")
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    if other_room:
        dialog.get_by_role("button", name="Close").click()
        page.goto(app_url(svelte_server, f"room/{slug}"))
        page.get_by_label("Room Password").fill(CABIN_PASSWORD)
        page.get_by_label("Room Password").press("Enter")
        expect(page.get_by_role("button", name="Add New List")).to_be_visible()
        dialog = open_settings(page)
    else:
        dialog.get_by_role("button", name="Opt out of this room").click()
        expect(dialog.get_by_text("Status: Opted out")).to_be_visible()
    dialog.get_by_label("Room reminder mode").select_option("daily_summary")
    dialog.get_by_label("Room summary time").fill("12:34")
    edit_device_draft(dialog)
    page.evaluate(
        """corrupt => {
        const real = window.fetch;
        window.enrollmentAttempts = [];
        window.fetch = async (...args) => {
            const isEnrollment = String(args[0]).endsWith('/reminders/enrollment') && args[1]?.method === 'POST';
            if (isEnrollment) window.enrollmentAttempts.push(JSON.parse(args[1].body));
            const response = await real(...args);
            if (isEnrollment && corrupt && window.enrollmentAttempts.length === 1) {
                if (response.status !== 200) throw new Error('First enrollment failed');
                return new Response('{', {status: 200, headers: {'Content-Type': 'application/json'}});
            }
            return response;
        };
    }""",
        unknown,
    )
    if unknown:
        dialog.get_by_role(
            "button", name="Enroll this device" if other_room else "Resume this room"
        ).click()
        expect(dialog.get_by_role("alert")).to_contain_text("result is unknown")
    with sqlite3.connect(svelte_server.database) as db:
        db.execute(
            "UPDATE reminder_installations SET expires_at = '2000-01-01T00:00:00Z'"
        )
    dialog.get_by_role(
        "button",
        name="Retry request"
        if unknown
        else ("Enroll this device" if other_room else "Resume this room"),
    ).click()
    expect(dialog.get_by_text("Status: Not enrolled")).to_be_visible()
    expect(dialog.get_by_role("alert")).to_contain_text("unavailable or expired")
    attempts = page.evaluate("window.enrollmentAttempts")
    if unknown:
        expect(dialog.get_by_role("alert")).to_contain_text(
            "previous request may have committed"
        )
        assert len(attempts) == 2 and attempts[0] == attempts[1]
    else:
        assert len(attempts) == 1
    assert all("timezone" not in body for body in attempts)
    expect(dialog.get_by_label("Room summary time")).to_have_value("12:34")
    expect(dialog.get_by_label("Room reminder mode")).to_have_value("daily_summary")
    dialog.get_by_text("Change time zone", exact=True).click()
    expect(dialog.get_by_label("Time zone for this device")).to_have_value(
        "Europe/Oslo"
    )
    assert svelte_server.query("SELECT COUNT(*) FROM reminder_installations") == [(1,)]
    old_id = attempts[-1]["op_id"]
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    attempts = page.evaluate("window.enrollmentAttempts")
    assert attempts[-1]["op_id"] != old_id and attempts[-1]["timezone"] == "Europe/Oslo"
    expect(dialog.get_by_label("All-day reminder time")).to_have_value("13:25")
    expect(dialog.get_by_label("Pause reminders on this device")).to_be_checked()
    assert svelte_server.query("SELECT COUNT(*) FROM reminder_installations") == [(2,)]


def test_enrollment_422_retains_real_validation_error(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    dialog.get_by_role("button", name="Opt out of this room").click()
    expect(dialog.get_by_text("Status: Opted out")).to_be_visible()
    dialog.get_by_label("Room summary time").fill("")
    dialog.get_by_role("button", name="Resume this room").click()
    expect(dialog.get_by_role("alert")).to_contain_text("Enter summary time as HH:MM")
    expect(dialog.get_by_role("alert")).not_to_contain_text("unavailable or expired")
    expect(dialog.get_by_text("Status: Opted out")).to_be_visible()
    expect(dialog.get_by_label("Room summary time")).to_have_value("")
    assert svelte_server.query("SELECT COUNT(*) FROM reminder_installations") == [(1,)]


def test_enrollment_expiry_identity_load_failure_keeps_unknown_warning(
    svelte_server, open_session
):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    dialog.get_by_role("button", name="Opt out of this room").click()
    expect(dialog.get_by_text("Status: Opted out")).to_be_visible()
    dialog.get_by_label("Room summary time").fill("12:34")
    page.evaluate("""() => {
        const real = window.fetch;
        let corrupt = true;
        window.failIdentityReads = false;
        window.fetch = async (...args) => {
            if (window.failIdentityReads && args[1]?.method === 'GET' && String(args[0]).includes('/reminders/preferences')) throw new TypeError('offline');
            const response = await real(...args);
            if (corrupt && String(args[0]).endsWith('/reminders/enrollment') && args[1]?.method === 'POST') {
                corrupt = false;
                if (response.status !== 200) throw new Error('First enrollment failed');
                return new Response('{', {status: 200});
            }
            return response;
        };
    }""")
    dialog.get_by_role("button", name="Resume this room").click()
    expect(dialog.get_by_role("alert")).to_contain_text("result is unknown")
    with sqlite3.connect(svelte_server.database) as db:
        db.execute(
            "UPDATE reminder_installations SET expires_at = '2000-01-01T00:00:00Z'"
        )
    page.evaluate("window.failIdentityReads = true")
    dialog.get_by_role("button", name="Retry request").click()
    expect(dialog.get_by_role("alert")).to_contain_text(
        "previous request may have committed"
    )
    expect(dialog.get_by_role("button", name="Try loading again")).to_be_visible()
    expect(dialog.get_by_text("Status: Opted out")).to_have_count(0)
    page.evaluate("window.failIdentityReads = false")
    dialog.get_by_role("button", name="Try loading again").click()
    expect(dialog.get_by_text("Status: Not enrolled")).to_be_visible()
    expect(dialog.get_by_role("alert")).to_contain_text(
        "previous request may have committed"
    )
    expect(dialog.get_by_label("Room summary time")).to_have_value("12:34")
    assert svelte_server.query("SELECT COUNT(*) FROM reminder_installations") == [(1,)]


def test_conflict_requires_reload_and_preserves_draft(svelte_server, open_session):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    result = page.evaluate(
        """async slug => {
        const url = `/api/v1/rooms/${slug}/reminders/preferences`;
        const current = await (await fetch(url)).json();
        const response = await fetch(url, {
            method: 'PATCH', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({op_id: crypto.randomUUID(), base_revision: current.enrollment.revision, mode: 'quiet'})
        });
        return response.status;
    }""",
        svelte_server.room_slug,
    )
    assert result == 200
    dialog.get_by_label("Room summary time").fill("11:45")
    dialog.get_by_role("button", name="Save room settings").click()
    expect(dialog.get_by_role("alert")).to_contain_text("Settings changed elsewhere")
    expect(dialog.get_by_role("button", name="Save room settings")).to_be_disabled()
    dialog.get_by_role("button", name="Load latest revisions").click()
    expect(dialog.get_by_label("Room summary time")).to_have_value("11:45")
    expect(dialog.get_by_role("button", name="Save room settings")).to_be_enabled()


def test_device_settings_are_private_to_each_installation(svelte_server, open_session):
    first = open_session("first", **PHONE)
    second = open_session("second", **PHONE)
    sign_in(first, svelte_server)
    sign_in(second, svelte_server)
    first_dialog = open_settings(first)
    first_dialog.get_by_role("button", name="Enroll this device").click()
    expect(first_dialog.get_by_text("Status: Active")).to_be_visible()
    first_dialog.get_by_label("All-day reminder time").fill("13:25")
    first_dialog.get_by_role("button", name="Save device settings").click()
    expect(first_dialog.get_by_role("status")).to_have_text("Saved on this device.")
    second_dialog = open_settings(second)
    second_dialog.get_by_role("button", name="Enroll this device").click()
    expect(second_dialog.get_by_text("Status: Active")).to_be_visible()
    expect(second_dialog.get_by_label("All-day reminder time")).to_have_value("09:00")
    expect(first_dialog.get_by_label("All-day reminder time")).to_have_value("13:25")


def test_share_visitor_has_no_personal_controls(svelte_server, open_session):
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, svelte_server)
    create_list(member, "Groceries")
    visitor.goto(share_link(member))
    expect(visitor.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(visitor.get_by_role("button", name="Room menu")).to_have_count(0)
    expect(visitor.get_by_text("Personal reminders")).to_have_count(0)


def test_device_controls_persist_and_retry_exact_unknown_write(
    svelte_server, open_session
):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    expect(
        dialog.get_by_text("These apply to every room enrolled on this device.")
    ).to_be_visible()
    expect(dialog.get_by_label("Enable quiet hours")).to_be_checked()
    expect(dialog.get_by_label("Quiet hours start")).to_have_value("22:00")
    expect(dialog.get_by_label("Quiet hours end")).to_have_value("08:00")
    expect(dialog.get_by_label("Daily cap (1\u201350)")).to_have_value("10")
    expect(dialog.get_by_label("Minimum spacing in minutes (1\u201360)")).to_have_value(
        "10"
    )
    expect(dialog.get_by_label("Notification content privacy")).to_have_value("generic")
    expect(dialog.get_by_label("Enable overdue repeat")).not_to_be_checked()
    dialog.get_by_label("Quiet hours start").fill("21:15")
    dialog.get_by_label("Quiet hours end").fill("07:30")
    dialog.get_by_label("Daily cap (1\u201350)").fill("23")
    dialog.get_by_label("Minimum spacing in minutes (1\u201360)").fill("17")
    dialog.get_by_label("Notification content privacy").select_option("names")
    dialog.get_by_label("Enable overdue repeat").check()
    dialog.get_by_label("Overdue repeat interval in days (1\u201330)").fill("9")
    bodies = []

    def corrupt_first(route):
        if route.request.method != "PATCH":
            route.continue_()
            return
        bodies.append(route.request.post_data)
        if len(bodies) == 1:
            response = route.fetch()
            assert response.status == 200
            route.fulfill(response=response, body="{}")
        else:
            route.continue_()

    page.route("**/reminders/preferences/device", corrupt_first)
    dialog.get_by_role("button", name="Save device settings").click()
    expect(dialog.get_by_role("button", name="Retry request")).to_be_visible()
    expect(dialog.get_by_label("Quiet hours start")).to_be_disabled()
    expect(dialog.get_by_label("Notification content privacy")).to_be_disabled()
    dialog.get_by_role("button", name="Retry request").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    body = json.loads(bodies[0])
    assert (
        body["quiet_hours"],
        body["daily_cap"],
        body["spacing_minutes"],
        body["content_privacy"],
        body["overdue_repeat_days"],
    ) == ({"start": "21:15", "end": "07:30"}, 23, 17, "names", 9)
    page.unroute("**/reminders/preferences/device", corrupt_first)
    dialog.get_by_role("button", name="Close").click()
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Personal reminders", exact=True).click()
    dialog = page.get_by_role("dialog", name="Personal reminders")
    expect(dialog.get_by_label("Quiet hours start")).to_have_value("21:15")
    expect(dialog.get_by_label("Quiet hours end")).to_have_value("07:30")
    expect(dialog.get_by_label("Daily cap (1\u201350)")).to_have_value("23")
    expect(dialog.get_by_label("Minimum spacing in minutes (1\u201360)")).to_have_value(
        "17"
    )
    expect(dialog.get_by_label("Notification content privacy")).to_have_value("names")
    expect(dialog.get_by_label("Enable overdue repeat")).to_be_checked()
    expect(
        dialog.get_by_label("Overdue repeat interval in days (1\u201330)")
    ).to_have_value("9")
    dialog.get_by_label("Enable quiet hours").uncheck()
    dialog.get_by_label("Enable overdue repeat").uncheck()
    dialog.get_by_role("button", name="Save device settings").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    dialog.get_by_role("button", name="Close").click()
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Personal reminders", exact=True).click()
    dialog = page.get_by_role("dialog", name="Personal reminders")
    expect(dialog.get_by_label("Enable quiet hours")).not_to_be_checked()
    expect(dialog.get_by_label("Enable overdue repeat")).not_to_be_checked()
    expect(dialog.get_by_label("Quiet hours start")).to_have_count(0)
    expect(
        dialog.get_by_label("Overdue repeat interval in days (1\u201330)")
    ).to_have_count(0)


def test_device_controls_reject_invalid_bounds_and_preserve_offline_draft(
    svelte_server, open_session
):
    page = open_session("owner", **PHONE)
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    writes = []
    page.on(
        "request",
        lambda request: (
            writes.append(request.post_data)
            if request.method == "PATCH"
            and request.url.endswith("/reminders/preferences/device")
            else None
        ),
    )
    dialog.get_by_label("Enable overdue repeat").check()
    for label, values, valid in (
        ("Daily cap (1\u201350)", ("0", "51", "1.5", ""), "10"),
        ("Minimum spacing in minutes (1\u201360)", ("0", "61", "1.5", ""), "10"),
        ("Overdue repeat interval in days (1\u201330)", ("0", "31", "1.5", ""), "1"),
    ):
        for value in values:
            dialog.get_by_label(label).fill(value)
            dialog.get_by_role("button", name="Save device settings").click()
            expect(dialog.get_by_role("alert")).to_contain_text("whole numbers")
            assert not writes
        dialog.get_by_label(label).fill(valid)
    dialog.get_by_label("Quiet hours end").fill("22:00")
    dialog.get_by_role("button", name="Save device settings").click()
    expect(dialog.get_by_role("alert")).to_contain_text("different start and end")
    assert not writes
    dialog.get_by_label("Quiet hours end").fill("08:00")
    dialog.get_by_label("Daily cap (1\u201350)").fill("42")
    page.context.set_offline(True)
    expect(dialog.get_by_role("button", name="Save device settings")).to_be_disabled()
    expect(dialog.get_by_label("Daily cap (1\u201350)")).to_have_value("42")
    page.context.set_offline(False)
    expect(dialog.get_by_role("button", name="Save device settings")).to_be_enabled()
    expect(dialog.get_by_label("Daily cap (1\u201350)")).to_have_value("42")
    assert not writes


def test_time_settings_oslo_and_24_hour_controls(svelte_server, open_session):
    page = open_session("owner", **PHONE, locale="en-US")
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    expect(dialog.get_by_text("Time zone: Europe/Oslo", exact=True)).to_be_visible()
    expect(dialog.get_by_label("Room summary time")).to_have_attribute("type", "text")
    dialog.get_by_label("Room summary time").fill("13:45")
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    expect(dialog.get_by_text("Device time zone: Europe/Oslo")).to_be_visible()
    dialog.get_by_label("Room reminder mode").select_option("quiet")
    expect(dialog.get_by_label("Room summary time")).to_have_count(0)
    dialog.get_by_label("Room reminder mode").select_option("custom")
    expect(dialog.get_by_role("button", name="Edit custom room rules")).to_be_visible()
    dialog.get_by_role("button", name="Save room settings").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    dialog.get_by_role("button", name="Edit custom room rules").click()
    editor = page.get_by_role("dialog", name="Personal room reminders")
    expect(editor.get_by_role("button", name="Add relative rule")).to_be_visible()


def test_custom_summary_and_invalid_24_hour_time(svelte_server, open_session):
    page = open_session("owner", **PHONE, locale="en-US")
    sign_in(page, svelte_server)
    dialog = open_settings(page)
    summary = dialog.get_by_label("Room summary time")
    summary.fill("24:00")
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_role("alert")).to_contain_text("HH:MM")
    expect(dialog.get_by_text("Status: Not enrolled")).to_be_visible()
    summary.fill("13:45")
    dialog.get_by_role("button", name="Enroll this device").click()
    expect(dialog.get_by_text("Status: Active")).to_be_visible()
    for mode in ("quiet", "scheduled", "custom"):
        dialog.get_by_label("Room reminder mode").select_option(mode)
        expect(dialog.get_by_label("Room summary time")).to_have_count(0)
    dialog.get_by_role("button", name="Save room settings").click()
    expect(dialog.get_by_role("status")).to_have_text("Saved on this device.")
    dialog.get_by_role("button", name="Edit custom room rules").click()
    editor = page.get_by_role("dialog", name="Personal room reminders")
    editor.get_by_label("Include daily summary").check()
    editor.get_by_role("button", name="Save policy").click()
    expect(editor.get_by_text("Saved on this device.")).to_be_visible()
    editor.get_by_role("button", name="Close").click()
    expect(dialog.get_by_label("Room summary time")).to_have_value("13:45")
    dialog.get_by_label("Room reminder mode").select_option("scheduled")
    expect(dialog.get_by_label("Room summary time")).to_have_count(0)
    dialog.get_by_label("Room reminder mode").select_option("custom")
    expect(dialog.get_by_label("Room summary time")).to_have_value("13:45")
