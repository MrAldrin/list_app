"""Two devices, one list, offline: the merge and conflict rules R1-R7.

docs/background/offline-editing-details.md, "Conflict rules". Each browser context is its own
device, so each one can be offline on its own. Offline is simulated by failing
every API call (`go_offline`). The rules that a single device does not hit
(revoked access, a list rename, storage loss, a new version) are covered here
too, on one device.
"""

import json
import re

from playwright.sync_api import Page, expect
from svelte_app import (
    add_item,
    create_list,
    item_names,
    room_app_url,
    sign_in,
    wait_until,
)
from test_svelte_offline_reconnect import (
    NO_WORKER,
    SLOW,
    go_offline,
    go_online,
    member_with_list,
    saved_notice,
    view_offline,
)

from api.version import API_VERSION

OTHER_VERSION = str(API_VERSION + 1)
API_ROUTES = re.compile(r".*/api/v1/(?!.*/events).*")
OPS = re.compile(r".*/api/v1/rooms/[^/]+/ops$")

# Deletes every database of this site, as a browser does when it clears site data.
CLEAR_SITE_DATA = """async () => {
    for (const { name } of await indexedDB.databases()) {
        await new Promise((resolve, reject) => {
            const request = indexedDB.deleteDatabase(name);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
}"""


def item_row(page: Page, name: str):
    return page.locator("ul.items > li", has=page.get_by_role("checkbox", name=name))


def not_sent_mark(page: Page, name: str):
    return item_row(page, name).get_by_role("img", name="Not sent yet")


def tags_of(server, name: str) -> list[str]:
    [(raw,)] = server.query("SELECT active_tags FROM items WHERE name = ?", (name,))
    return json.loads(raw)


def two_devices_on_list(open_session, server, first: str, second: str, items=("milk",)):
    """Signed in on one list on two devices. Both have the list saved.

    Returns (first device, second device, list URL). Both are online here.
    """
    phone, url = member_with_list(open_session, server, first, items=items)
    other = open_session(second, **NO_WORKER)
    sign_in(other, server)
    other.goto(url)
    expect(item_names(other)).to_have_text(sorted(items))
    return phone, other, url


def test_both_offline_quantity_taps_both_count(svelte_server, open_session):
    """R1: a +1 on each device, both offline, make +2 in total."""
    server = svelte_server
    phone, other, url = two_devices_on_list(open_session, server, "r1-a", "r1-b")
    assert server.query("SELECT quantity FROM items WHERE name = 'milk'") == [(1,)]

    for page in (phone, other):
        view_offline(page, url)
        page.get_by_role("button", name="Options").click()
        page.get_by_role("switch", name="Show quantities").check()
        page.get_by_role("button", name="Done").click()
        expect(page.get_by_role("button", name="More milk")).to_be_enabled()
    for page in (phone, other):
        page.get_by_role("button", name="More milk").click()

    go_online(phone)
    go_online(other)
    wait_until(
        phone,
        lambda: (
            server.query("SELECT quantity FROM items WHERE name = 'milk'") == [(3,)]
        ),
        "the two +1 taps did not both reach the server",
        timeout_ms=20_000,
    )
    for page in (phone, other):
        expect(
            page.get_by_role("group", name="Quantity of milk").get_by_text(
                "3", exact=True
            )
        ).to_be_visible(**SLOW)
        expect(not_sent_mark(page, "milk")).to_have_count(0)
        expect(page.get_by_text("was not saved")).to_have_count(0)


def test_both_offline_ticks_on_one_item_apply_without_a_conflict(
    svelte_server, open_session
):
    """R2: the same tick from two devices is applied once, with no conflict shown."""
    server = svelte_server
    phone, other, url = two_devices_on_list(open_session, server, "r2-a", "r2-b")

    for page in (phone, other):
        view_offline(page, url)
        page.get_by_role("checkbox", name="milk").check()
        expect(not_sent_mark(page, "milk")).to_be_visible()

    go_online(phone)
    go_online(other)
    wait_until(
        phone,
        lambda: server.query("SELECT done FROM items WHERE name = 'milk'") == [(1,)],
        "the tick did not reach the server",
        timeout_ms=20_000,
    )
    for page in (phone, other):
        expect(not_sent_mark(page, "milk")).to_have_count(0, **SLOW)
        expect(page.get_by_role("checkbox", name="milk")).to_be_checked()
        expect(page.get_by_text("was not saved")).to_have_count(0)


def test_one_device_offline_ticks_then_edits_the_same_item(svelte_server, open_session):
    """R3: the device's own tick and edit on one item are both saved, no conflict."""
    server = svelte_server
    phone, other, url = two_devices_on_list(open_session, server, "r3-a", "r3-b")

    view_offline(phone, url)
    phone.get_by_role("checkbox", name="milk").check()
    expect(not_sent_mark(phone, "milk")).to_be_visible()
    phone.get_by_role("button", name="milk", exact=True).click()
    dialog = phone.get_by_role("dialog")
    dialog.get_by_label("Description / Notes").fill("2 litres")
    dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_have_count(0)

    go_online(phone)
    wait_until(
        phone,
        lambda: (
            server.query("SELECT done, description FROM items WHERE name = 'milk'")
            == [(1, "2 litres")]
        ),
        "the tick and the edit did not both reach the server",
        timeout_ms=20_000,
    )
    expect(not_sent_mark(phone, "milk")).to_have_count(0)
    expect(phone.get_by_text("was not saved")).to_have_count(0)
    # The other device stays online and gets both changes.
    expect(other.get_by_role("checkbox", name="milk")).to_be_checked(**SLOW)


def test_both_offline_add_the_same_tag_to_an_item_once(svelte_server, open_session):
    """R4: the same tag added on two devices is on the item once, no conflict."""
    server = svelte_server
    phone, url = member_with_list(open_session, server, "r4-a")
    phone.get_by_role("button", name="Options").click()
    tag = phone.get_by_label("Add Tag")
    tag.fill("Market")
    tag.press("Enter")
    phone.get_by_role("button", name="Done").click()
    expect(phone.get_by_role("button", name="Market tag for milk")).to_be_visible()

    other = open_session("r4-b", **NO_WORKER)
    sign_in(other, server)
    other.goto(url)
    expect(other.get_by_role("button", name="Market tag for milk")).to_be_visible()

    for page in (phone, other):
        view_offline(page, url)
        page.get_by_role("button", name="Market tag for milk").click()
        expect(
            page.get_by_role("button", name="Market tag for milk")
        ).to_have_attribute("aria-pressed", "true")

    go_online(phone)
    go_online(other)
    wait_until(
        phone,
        lambda: tags_of(server, "milk") == ["Market"],
        "the tag did not reach the server once",
        timeout_ms=20_000,
    )
    for page in (phone, other):
        expect(not_sent_mark(page, "milk")).to_have_count(0)
        expect(page.get_by_text("was not saved")).to_have_count(0)
    assert tags_of(server, "milk") == ["Market"]


def test_edit_of_an_item_deleted_elsewhere_refuses_a_tick_offline(
    svelte_server, open_session
):
    """R5: device A deletes the item online; device B, offline, ticks it."""
    server = svelte_server
    phone, other, url = two_devices_on_list(open_session, server, "r5-b", "r5-a")

    view_offline(phone, url)
    phone.get_by_role("checkbox", name="milk").check()
    expect(not_sent_mark(phone, "milk")).to_be_visible()

    other.get_by_role("button", name="Options").click()
    other.get_by_role("button", name="Delete milk", exact=True).click()
    other.get_by_role("button", name="Done").click()
    wait_until(
        other,
        lambda: (
            server.query("SELECT count(*) FROM items WHERE name = 'milk'") == [(0,)]
        ),
        "the delete did not reach the server",
    )

    go_online(phone)
    expect(phone.get_by_text("1 change was not saved")).to_be_visible(**SLOW)
    phone.get_by_role("button", name="Review").click()
    dialog = phone.get_by_role("dialog")
    expect(
        dialog.get_by_text("Tick 'milk': it was deleted by someone else.")
    ).to_be_visible()
    expect(dialog.get_by_role("button", name="Save mine anyway")).to_have_count(0)
    # The "Checked milk" toast inside the dialog has its own "Dismiss" button.
    dialog.get_by_text("Dismiss", exact=True).click()
    expect(phone.get_by_role("dialog")).to_have_count(0)
    expect(phone.get_by_text("was not saved")).to_have_count(0)
    assert server.query("SELECT count(*) FROM items WHERE name = 'milk'") == [(0,)]


def test_both_offline_add_the_same_new_item_makes_one_item(svelte_server, open_session):
    """R6: both add "bread" offline; B then ticks its own "bread", which lands on the one item."""
    server = svelte_server
    phone, other, url = two_devices_on_list(open_session, server, "r6-a", "r6-b")

    view_offline(phone, url)
    add_item(phone, "bread")
    expect(item_names(phone)).to_have_text(["bread", "milk"])

    view_offline(other, url)
    add_item(other, "bread")
    other.get_by_role("checkbox", name="bread").check()
    expect(item_names(other)).to_have_count(2)

    go_online(phone)
    wait_until(
        phone,
        lambda: (
            server.query("SELECT name FROM items WHERE name = 'bread'") == [("bread",)]
        ),
        "the first bread did not reach the server",
        timeout_ms=20_000,
    )

    go_online(other)
    wait_until(
        other,
        lambda: (
            server.query("SELECT name, done FROM items WHERE name = 'bread'")
            == [("bread", 1)]
        ),
        "the tick on the second device did not land on the one bread",
        timeout_ms=20_000,
    )
    assert server.query("SELECT count(*) FROM items WHERE name = 'bread'") == [(1,)]
    for page in (phone, other):
        expect(item_names(page)).to_have_count(2, timeout=SLOW["timeout"])
        expect(not_sent_mark(page, "bread")).to_have_count(0)
        expect(page.get_by_text("was not saved")).to_have_count(0)
    expect(phone.get_by_role("checkbox", name="bread")).to_be_checked(**SLOW)


def room_with_two_lists(open_session, server, role: str) -> Page:
    page = open_session(role, **NO_WORKER)
    sign_in(page, server)
    create_list(page, "Groceries")
    page.goto(room_app_url(server))
    create_list(page, "Hardware")
    page.goto(room_app_url(server))
    expect(page.get_by_role("button", name="Rename Groceries")).to_be_visible()
    return page


def rename_list(page: Page, current: str, new_name: str) -> None:
    page.get_by_role("button", name=f"Rename {current}").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("List Name").fill(new_name)
    dialog.get_by_role("button", name="Save").click()
    expect(page.get_by_role("dialog")).to_have_count(0)


def test_both_offline_rename_two_lists_to_one_name_refuses_the_second(
    svelte_server, open_session
):
    """R7: two lists renamed to the same name, offline: one is saved, one is listed as not saved."""
    server = svelte_server
    phone = room_with_two_lists(open_session, server, "r7-a")
    other = open_session("r7-b", **NO_WORKER)
    sign_in(other, server)
    expect(other.get_by_role("button", name="Rename Hardware")).to_be_visible()

    for page, current in ((phone, "Groceries"), (other, "Hardware")):
        go_offline(page)
        # The room's live stream is cut by this navigation; WebKit reports that.
        page.expects_reload_cancel = True
        page.goto(room_app_url(server))
        expect(saved_notice(page)).to_be_visible()
        rename_list(page, current, "Shopping")

    go_online(phone)
    wait_until(
        phone,
        lambda: (
            server.query("SELECT name FROM lists WHERE name = 'Shopping'")
            == [("Shopping",)]
        ),
        "the first rename did not reach the server",
        timeout_ms=20_000,
    )
    go_online(other)
    expect(other.get_by_text("1 change was not saved")).to_be_visible(**SLOW)
    other.get_by_role("button", name="Review").click()
    dialog = other.get_by_role("dialog")
    expect(
        dialog.get_by_text("Rename list to 'Shopping': that name is taken.")
    ).to_be_visible()
    dialog.get_by_text("Dismiss", exact=True).click()
    expect(other.get_by_role("dialog")).to_have_count(0)

    assert server.query("SELECT name FROM lists ORDER BY name") == [
        ("Hardware",),
        ("Shopping",),
    ]
    expect(other.get_by_role("button", name="Rename Hardware")).to_be_visible()
    expect(phone.get_by_role("button", name="Rename Shopping")).to_be_visible(**SLOW)


def test_cleared_site_data_drops_waiting_changes_and_the_page_still_loads(
    svelte_server, open_session
):
    """Storage loss (R11): the browser clears the site's data with a change waiting."""
    server = svelte_server
    phone, url = member_with_list(open_session, server, "cleared")
    view_offline(phone, url)
    phone.get_by_role("checkbox", name="milk").check()
    expect(not_sent_mark(phone, "milk")).to_be_visible()

    phone.evaluate(CLEAR_SITE_DATA)
    phone.reload()
    # Nothing is saved for this device now, so the page says it cannot load.
    expect(phone.get_by_text("Connect to load this list.")).to_be_visible()
    expect(saved_notice(phone)).to_have_count(0)
    expect(phone.get_by_text("waiting to be sent")).to_have_count(0)

    go_online(phone)
    expect(item_names(phone)).to_have_text(["bread", "milk"], **SLOW)
    expect(phone.get_by_role("checkbox", name="milk")).not_to_be_checked()
    expect(not_sent_mark(phone, "milk")).to_have_count(0)
    # Kept: the check is that the cleared change is never sent. No UI signal
    # marks an unsent change, so this window is the only check.
    phone.wait_for_timeout(500)
    assert server.query("SELECT done FROM items WHERE name = 'milk'") == [(0,)]
    expect(phone.get_by_text("was not saved")).to_have_count(0)


def test_waiting_change_survives_a_reload_onto_a_new_version(
    svelte_server, open_session
):
    """A new API version while a change waits: a reload keeps it, then it is sent.

    The server is not really replaced here (the build stays the same). The
    page sees another X-Api-Version, the change is stored but not sent, the
    page reloads with the change still stored, and after the server answers
    with the expected version, the reload sends it.
    """
    server = svelte_server
    page = open_session("update-waiting", **NO_WORKER)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")

    def answer_with(version: str):
        def handler(route):
            response = route.fetch()
            route.fulfill(
                response=response,
                headers={**response.headers, "x-api-version": version},
            )

        return handler

    def busy_new_server(route):
        route.fulfill(
            status=503,
            headers={
                "x-api-version": OTHER_VERSION,
                "content-type": "application/json",
            },
            body='{"error": {"code": "unavailable", "message": "Busy"}}',
        )

    page.route(API_ROUTES, answer_with(OTHER_VERSION))
    page.route(OPS, busy_new_server)
    page.get_by_role("checkbox", name="milk").check()
    notice = page.get_by_role("alert").filter(has_text="A new version is available")
    expect(notice).to_contain_text("1 change is saved on this phone")
    expect(not_sent_mark(page, "milk")).to_be_visible()
    assert server.query("SELECT done FROM items WHERE name = 'milk'") == [(0,)]

    # The page reloads while the server still answers the other version.
    page.reload()
    expect(notice).to_contain_text("1 change is saved on this phone")
    expect(notice).not_to_contain_text("will lose")
    # The waiting tick is still shown, and still marked as not sent.
    expect(page.get_by_role("checkbox", name="milk")).to_be_checked()
    expect(not_sent_mark(page, "milk")).to_be_visible()
    # Kept: the check is that the tick is not sent on reload. No UI signal
    # marks that, so this window is the only check.
    page.wait_for_timeout(300)
    assert server.query("SELECT done FROM items WHERE name = 'milk'") == [(0,)]

    # The server answers the expected version again; Reload sends the change.
    page.unroute(OPS)
    page.unroute(API_ROUTES)
    with page.expect_navigation():
        notice.get_by_role("button", name="Reload").click()
    expect(page.get_by_role("checkbox", name="milk")).to_be_checked(**SLOW)
    expect(not_sent_mark(page, "milk")).to_have_count(0)
    expect(notice).to_have_count(0)
    wait_until(
        page,
        lambda: server.query("SELECT done FROM items WHERE name = 'milk'") == [(1,)],
        "the change stored before the reload was not sent",
        timeout_ms=20_000,
    )
