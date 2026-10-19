"""Waiting, refused and conflicting changes: the Not saved list, access gone, marks and hints.

Offline is simulated by failing every API call (`go_offline`), as in
test_svelte_offline_reconnect.py. A second browser context is "another device".
"""

from playwright.sync_api import expect
from svelte_app import (
    add_item,
    item_names,
    sign_in,
    wait_until,
)
from test_svelte_offline_reconnect import (
    NO_WORKER,
    SLOW,
    go_online,
    member_with_list,
    view_offline,
)

NEW_PASSWORD = "new-room-password"


def item_row(page, name: str):
    return page.locator("ul.items > li", has=page.get_by_role("checkbox", name=name))


def make_first_queue_entry_old(page, room_slug: str) -> None:
    page.evaluate(
        """async (slug) => {
            const db = await new Promise((resolve, reject) => {
                const request = indexedDB.open('listr-queue', 1);
                request.onsuccess = () => resolve(request.result);
                request.onerror = () => reject(request.error);
            });
            let record;
            for (let attempt = 0; attempt < 100; attempt += 1) {
                const tx = db.transaction('queue', 'readonly');
                record = await new Promise((resolve, reject) => {
                    const request = tx.objectStore('queue').get(`room:${slug}`);
                    request.onsuccess = () => resolve(request.result);
                    request.onerror = () => reject(request.error);
                });
                if (record?.entries?.length) break;
                await new Promise((resolve) => setTimeout(resolve, 10));
            }
            if (!record?.entries?.length) throw new Error('the room queue was not stored');
            const tx = db.transaction('queue', 'readwrite');
            record.entries[0].at = new Date(Date.now() - 31 * 24 * 60 * 60 * 1000).toISOString();
            tx.objectStore('queue').put(record);
            await new Promise((resolve, reject) => {
                tx.oncomplete = resolve;
                tx.onerror = () => reject(tx.error);
                tx.onabort = () => reject(tx.error);
            });
            db.close();
        }""",
        room_slug,
    )


def test_refused_tick_is_listed_and_save_mine_anyway_applies(
    svelte_server, open_session
):
    """A ticks offline; B edits the item; A's tick is refused, then re-sent as a new change."""
    server = svelte_server
    phone, url = member_with_list(open_session, server, "phone-a")
    view_offline(phone, url)
    phone.get_by_role("checkbox", name="milk").check()
    expect(
        item_row(phone, "milk").get_by_role("img", name="Not sent yet")
    ).to_be_visible()

    other = open_session("device-b", **NO_WORKER)
    sign_in(other, server)
    other.goto(url)
    expect(other.get_by_role("checkbox", name="milk")).to_be_visible()
    other.get_by_role("button", name="milk", exact=True).click()
    dialog = other.get_by_role("dialog")
    dialog.get_by_label("Description / Notes").fill("2 litres")
    dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_have_count(0)
    wait_until(
        other,
        lambda: (
            server.query("SELECT description FROM items WHERE name = 'milk'")
            == [("2 litres",)]
        ),
        "the other device's edit did not reach the server",
    )

    go_online(phone)
    expect(phone.get_by_text("1 change was not saved")).to_be_visible(**SLOW)
    retried_posts = []
    phone.on(
        "request",
        lambda request: (
            retried_posts.append(request.url)
            if request.method == "POST" and "/ops" in request.url
            else None
        ),
    )
    phone.reload()
    expect(phone.get_by_text("1 change was not saved")).to_be_visible(**SLOW)
    # Kept: the check is that no retry POST starts. Nothing visible marks that,
    # so this window is the only signal.
    phone.wait_for_timeout(300)
    assert retried_posts == []
    phone.get_by_role("button", name="Review").click()
    dialog = phone.get_by_role("dialog")
    expect(
        dialog.get_by_text("Tick 'milk': someone else changed it meanwhile.")
    ).to_be_visible()
    dialog.get_by_role("button", name="Save mine anyway", exact=True).click()

    # The sheet closes when nothing is left, and the change is on the server.
    expect(phone.get_by_role("dialog")).to_have_count(0)
    expect(phone.get_by_text("was not saved")).to_have_count(0)
    wait_until(
        phone,
        lambda: server.query("SELECT done FROM items WHERE name = 'milk'") == [(1,)],
        "the saved tick did not reach the server",
        timeout_ms=20_000,
    )
    expect(
        item_row(phone, "milk").get_by_role("img", name="Not sent yet")
    ).to_have_count(0)
    expect(phone.get_by_role("checkbox", name="milk")).to_be_checked()


def test_edit_of_an_item_another_device_deleted_is_listed_and_dismissed(
    svelte_server, open_session
):
    server = svelte_server
    phone, url = member_with_list(open_session, server, "phone-b")
    view_offline(phone, url)
    phone.get_by_role("button", name="milk", exact=True).click()
    dialog = phone.get_by_role("dialog")
    dialog.get_by_label("Item Name").fill("whole milk")
    dialog.get_by_role("button", name="Save").click()
    expect(dialog).to_have_count(0)
    expect(item_row(phone, "whole milk")).to_be_visible()

    other = open_session("device-b2", **NO_WORKER)
    sign_in(other, server)
    other.goto(url)
    other.get_by_role("button", name="Options").click()
    other.get_by_role("button", name="Delete milk", exact=True).click()
    expect(item_names(other)).to_have_text(["bread"])

    go_online(phone)
    expect(phone.get_by_text("1 change was not saved")).to_be_visible(**SLOW)
    phone.get_by_role("button", name="Review").click()
    dialog = phone.get_by_role("dialog")
    expect(
        dialog.get_by_text("Edit 'milk': it was deleted by someone else.")
    ).to_be_visible()
    expect(dialog.get_by_role("button", name="Save mine anyway")).to_have_count(0)
    dialog.get_by_role("button", name="Dismiss", exact=True).click()
    expect(phone.get_by_role("dialog")).to_have_count(0)
    expect(phone.get_by_text("was not saved")).to_have_count(0)


def test_access_gone_keeps_the_change_until_sign_in_sends_it(
    svelte_server, open_session
):
    """The room password changes elsewhere: the waiting add says it cannot be sent."""
    server = svelte_server
    phone, url = member_with_list(open_session, server, "phone-c")
    view_offline(phone, url)
    add_item(phone, "eggs")
    expect(item_names(phone)).to_have_text(["bread", "eggs", "milk"])

    other = open_session("device-c", **NO_WORKER)
    sign_in(other, server)
    other.get_by_role("button", name="Room menu").click()
    other.get_by_role("button", name="Change Password").click()
    other.get_by_label("Current Password").fill(server.password)
    other.get_by_label("New Password").fill(NEW_PASSWORD)
    other.get_by_role("button", name="Change").click()
    expect(other.get_by_text("Password changed successfully")).to_be_visible()

    go_online(phone)
    expect(
        phone.get_by_text("1 change can't be sent. Sign in again to send it.")
    ).to_be_visible(**SLOW)
    expect(phone.get_by_label("Room Password")).to_be_visible()
    phone.get_by_label("Room Password").fill(NEW_PASSWORD)
    phone.get_by_role("button", name="Enter").click()

    expect(item_names(phone)).to_have_text(["bread", "eggs", "milk"], timeout=20_000)
    expect(phone.get_by_text("can't be sent")).to_have_count(0)
    wait_until(
        phone,
        lambda: (
            server.query("SELECT name FROM items ORDER BY name")
            == [("bread",), ("eggs",), ("milk",)]
        ),
        "the change waiting for sign-in did not reach the server",
        timeout_ms=20_000,
    )


def test_unsent_marks_and_connection_hints_while_offline(svelte_server, open_session):
    server = svelte_server
    phone, url = member_with_list(open_session, server, "phone-d")
    view_offline(phone, url)
    phone.get_by_role("checkbox", name="milk").check()
    expect(
        item_row(phone, "milk").get_by_role("img", name="Not sent yet")
    ).to_be_visible()
    expect(
        item_row(phone, "bread").get_by_role("img", name="Not sent yet")
    ).to_have_count(0)

    phone.get_by_role("button", name="List menu").click()
    expect(phone.get_by_text("Needs a connection")).to_be_visible()
    described = phone.get_by_role("button", name="Share List").get_attribute(
        "aria-describedby"
    )
    assert described
    expect(phone.locator(f"[id='{described}']")).to_have_text("Needs a connection")
    phone.keyboard.press("Escape")

    go_online(phone)
    expect(
        item_row(phone, "milk").get_by_role("img", name="Not sent yet")
    ).to_have_count(0, timeout=20_000)
    wait_until(
        phone,
        lambda: server.query("SELECT done FROM items WHERE name = 'milk'") == [(1,)],
        "the offline tick did not reach the server",
        timeout_ms=20_000,
    )


def test_sign_out_with_waiting_changes_asks_first(svelte_server, open_session):
    server = svelte_server
    phone, url = member_with_list(open_session, server, "phone-e")
    view_offline(phone, url)
    phone.get_by_role("checkbox", name="milk").check()
    expect(
        item_row(phone, "milk").get_by_role("img", name="Not sent yet")
    ).to_be_visible()
    make_first_queue_entry_old(phone, server.room_slug)
    phone.reload()
    expect(phone.get_by_text("Offline — 1 change waiting to be sent.")).to_be_visible()
    phone.get_by_role("button", name="Review").click()
    old_dialog = phone.get_by_role("dialog")
    expect(old_dialog.get_by_text("Old changes not sent yet")).to_be_visible()
    expect(
        old_dialog.get_by_text(
            "These are in this room's queue on this device and were made more than 30 days ago. The server may no longer remember an earlier answer, so sending could apply them twice. They are sent only when you choose."
        )
    ).to_be_visible()
    phone.keyboard.press("Escape")
    expect(phone.get_by_role("dialog")).to_have_count(0)
    # In-app navigation, not a reload: the waiting change stays on this page.
    phone.get_by_role("link", name="Back to room").click()
    expect(phone.get_by_role("button", name="Add New List")).to_be_visible()
    expect(phone.get_by_text("1 change waiting to be sent.")).to_be_visible()

    phone.get_by_role("button", name="Room menu").click()
    phone.get_by_role("button", name="Log out").click()
    dialog = phone.get_by_role("dialog")
    expect(
        dialog.get_by_text(
            "1 waiting change in this room's queue on this device will be held after sign-out."
        )
    ).to_be_visible()
    expect(
        dialog.get_by_text(
            "After sign-in, choose Send or Discard. Changes older than 30 days need a separate send choice."
        )
    ).to_be_visible()
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    expect(phone.get_by_role("dialog")).to_have_count(0)
    expect(phone.get_by_role("button", name="Add New List")).to_be_visible()

    phone.get_by_role("button", name="Room menu").click()
    phone.get_by_role("button", name="Log out").click()
    phone.get_by_role("dialog").get_by_role(
        "button", name="Sign out", exact=True
    ).click()
    expect(phone.get_by_label("Room Password")).to_be_visible(**SLOW)
    expect(phone.get_by_text("1 change can't be sent")).to_be_visible(**SLOW)
    go_online(phone)
    phone.get_by_label("Room Password").fill(server.password)
    phone.get_by_role("button", name="Enter").click()
    expect(
        phone.get_by_text("1 change is held in this room's queue on this device.")
    ).to_be_visible(**SLOW)
    assert server.query("SELECT done FROM items WHERE name = 'milk'") == [(0,)]
    phone.get_by_role("button", name="Review").click()
    dialog = phone.get_by_role("dialog")
    expect(dialog.get_by_text("Changes held after sign-out")).to_be_visible()
    expect(dialog.get_by_text("Changes held after sign-out")).to_be_visible()
    expect(
        dialog.get_by_text(
            "These are in this room's queue on this device. They are not sent until you choose. Changes more than 30 days old stay held and need a separate choice."
        )
    ).to_be_visible()
    assert server.query("SELECT done FROM items WHERE name = 'milk'") == [(0,)]
    dialog.get_by_role("button", name="Send changes").click()
    expect(dialog.get_by_text("Old changes not sent yet")).to_be_visible()
    expect(
        dialog.get_by_text(
            "These are in this room's queue on this device and were made more than 30 days ago. The server may no longer remember an earlier answer, so sending could apply them twice. They are sent only when you choose."
        )
    ).to_be_visible()
    # Kept: proves that nothing is sent before the user chooses. No UI signal
    # marks an unsent change, so this window is the only check.
    phone.wait_for_timeout(300)
    assert server.query("SELECT done FROM items WHERE name = 'milk'") == [(0,)]
    dialog.get_by_role("button", name="Send all").click()
    wait_until(
        phone,
        lambda: server.query("SELECT done FROM items WHERE name = 'milk'") == [(1,)],
        "the explicitly approved old change did not reach the server",
        timeout_ms=20_000,
    )
