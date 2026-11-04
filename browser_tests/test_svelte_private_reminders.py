"""Private settings require an explicit enrollment and stay out of the shared queue."""

from playwright.sync_api import expect
from svelte_app import PHONE, create_list, share_link, sign_in
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
