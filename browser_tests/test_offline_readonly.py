"""Read-only snapshot storage and navigation fallback in real browser engines."""

import json
import re
import sqlite3

import pytest
from playwright.sync_api import expect

expect.set_options(timeout=10_000)


def prepare_snapshot_data(server):
    room_slug = server.query("SELECT slug FROM rooms WHERE name = 'Home'")[0][0]
    room_id = server.query("SELECT id FROM rooms WHERE slug = ?", (room_slug,))[0][0]
    unsafe_list_name = "<img src=x onerror=window.__offlineXss=1>"
    with sqlite3.connect(server.database) as connection:
        connection.execute(
            "INSERT INTO lists (name, list_tags, slug, room_id) VALUES (?, '[]', ?, ?)",
            ("Daily", "daily-list", room_id),
        )
        list_id = connection.execute(
            """
            INSERT INTO lists (name, list_tags, slug, room_id)
            VALUES (?, ?, ?, ?)
            """,
            (unsafe_list_name, '["seasonal"]', "never-opened", room_id),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO items (name, done, list_id, active_tags, description, quantity)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Checked apples", 1, list_id, '["produce"]', "Stored notes", 3),
        )
    default_slug = server.query(
        "SELECT slug FROM lists WHERE room_id = ? AND name = 'Daily'", (room_id,)
    )[0][0]
    return room_slug, default_slug, unsafe_list_name


def offline_record(page, room_slug):
    page.wait_for_function(
        """async (slug) => {
            const store = window.ListROfflineStorage;
            if (!store) return false;
            const record = await store.readRecord();
            return Boolean(record && record.snapshot.room.slug === slug);
        }""",
        arg=room_slug,
        timeout=15_000,
    )
    return page.evaluate("window.ListROfflineStorage.readRecord()")


@pytest.mark.parametrize("browser", ["chromium", "firefox"], indirect=True)
def test_one_room_snapshot_survives_offline_and_revalidates_on_return(server, sessions):
    member, _visitor = sessions
    room_slug, default_slug, unsafe_list_name = prepare_snapshot_data(server)
    room_url = f"{server.url}/room/{room_slug}"
    api_requests = []
    api_request_headers = []

    def record_request(request):
        api_requests.append(request.url)
        if "/api/offline/rooms/" in request.url:
            api_request_headers.append(request.headers)

    member.on("request", record_request)

    member.goto(room_url)
    member.get_by_label("Room Password", exact=True).fill(server.password)
    member.get_by_role("button", name="Enter", exact=True).click()
    expect(
        member.get_by_role("button", name="Add New List", exact=True)
    ).to_be_visible()

    record = offline_record(member, room_slug)
    assert record["schema_version"] == 1
    assert record["snapshot"]["room"]["slug"] == room_slug
    assert any(
        entry["name"] == unsafe_list_name for entry in record["snapshot"]["lists"]
    )
    token = member.evaluate(f"localStorage.getItem('listapp_room_token_{room_slug}')")
    assert token
    assert token not in json.dumps(record)
    assert token in api_request_headers[-1]["x-listapp-room-token"]
    assert all("?token=" not in url for url in api_requests)
    assert member.evaluate(
        """(slug) => {
            const valid = {schema_version: 1, room: {slug, name: 'Room'}, lists: []};
            return [
                window.ListROfflineStorage.validateSnapshot(valid, slug),
                window.ListROfflineStorage.validateSnapshot({...valid, token: 'secret'}, slug),
                window.ListROfflineStorage.validateSnapshot(valid, 'different-room'),
            ];
        }""",
        room_slug,
    ) == [True, False, False]

    member.wait_for_function(
        "navigator.serviceWorker.controller !== null", timeout=15_000
    )
    cached_paths = member.evaluate(
        """async () => {
            const cache = await caches.open('listr-offline-shell-v1');
            return (await cache.keys()).map((request) => new URL(request.url).pathname).sort();
        }"""
    )
    assert cached_paths == [
        "/static/offline-shell.css",
        "/static/offline-shell.html",
        "/static/offline-shell.js",
        "/static/offline-storage.js",
    ]
    assert not any("/api/" in path or "/room/" in path for path in cached_paths)

    # Force the next IndexedDB replacement to abort. The original record must remain intact.
    original_saved_at = record["saved_at"]
    endpoint = f"/api/offline/rooms/{room_slug}/snapshot"
    with member.expect_response(
        lambda response: endpoint in response.url and response.status == 200,
        timeout=15_000,
    ):
        member.goto(f"{server.url}/list/{default_slug}")
    member.wait_for_function(
        """async ({slug, previous}) => {
            const record = await window.ListROfflineStorage.readRecord();
            return record?.snapshot.room.slug === slug && record.saved_at !== previous;
        }""",
        arg={"slug": room_slug, "previous": original_saved_at},
        timeout=15_000,
    )
    stable_saved_at = member.evaluate(
        "window.ListROfflineStorage.readRecord().then((record) => record.saved_at)"
    )
    member.evaluate(
        """() => {
            window.__originalOfflinePut = IDBObjectStore.prototype.put;
            IDBObjectStore.prototype.put = function () {
                throw new DOMException('quota simulated by test', 'QuotaExceededError');
            };
        }"""
    )
    member.get_by_label("Add or Search", exact=True).fill("unsaved first attempt")
    member.get_by_role("button", name="Add", exact=True).click()
    expect(member.get_by_text("unsaved first attempt", exact=True)).to_be_visible()
    expect(
        member.get_by_text(re.compile("offline copy could not be updated"), exact=False)
    ).to_be_visible()
    preserved = member.evaluate("window.ListROfflineStorage.readRecord()")
    assert preserved["saved_at"] == stable_saved_at
    assert "unsaved first attempt" not in json.dumps(preserved)

    member.evaluate(
        """() => {
            IDBObjectStore.prototype.put = window.__originalOfflinePut;
            window.dispatchEvent(new Event('online'));
        }"""
    )
    member.wait_for_function(
        """async () => {
            const record = await window.ListROfflineStorage.readRecord();
            return JSON.stringify(record).includes('unsaved first attempt');
        }""",
        timeout=15_000,
    )

    # The open NiceGUI page offers a passive shell link after its connection drops.
    member.context.set_offline(True)
    expect(
        member.get_by_role("link", name="Open the read-only offline view", exact=True)
    ).to_be_visible()
    server.stop()
    # Another update is made while this browser is offline; the open shell refreshes on reconnect.
    member.goto(room_url, timeout=15_000)
    expect(member.get_by_text("Offline · read only", exact=True)).to_be_visible()
    expect(member.get_by_role("heading", name="Home", exact=True)).to_be_visible()
    expect(
        member.get_by_role("heading", name=unsafe_list_name, exact=True)
    ).to_be_visible()
    expect(member.get_by_text("Checked apples", exact=True)).to_be_visible()
    expect(member.get_by_text("Stored notes", exact=False)).to_be_visible()
    expect(member.get_by_text("Tags: seasonal", exact=False)).to_be_visible()
    expect(member.get_by_text("Tags: produce", exact=False)).to_be_visible()
    expect(member.get_by_text("quantity 3", exact=False)).to_be_visible()
    assert member.locator(".items li.done").count() == 1
    assert member.locator("input, button").count() == 0
    assert member.locator("img").count() == 0
    assert member.evaluate("window.__offlineXss") is None
    expect(member.get_by_text(re.compile("Last saved:"), exact=False)).to_be_visible()

    # A different room slug cannot use the one cached room, but root-launch icons can.
    member.goto(f"{server.url}/room/not-the-saved-room", timeout=15_000)
    expect(
        member.get_by_text("No offline copy is ready for this room.", exact=True)
    ).to_be_visible()
    assert member.get_by_text("Checked apples", exact=True).count() == 0
    member.goto(server.url, timeout=15_000)
    expect(member.get_by_text("Offline · read only", exact=True)).to_be_visible()
    expect(member.get_by_text("Checked apples", exact=True)).to_be_visible()

    # The shell performs an actual authorized fetch again when connectivity returns.
    room_id = server.query("SELECT id FROM rooms WHERE slug = ?", (room_slug,))[0][0]
    list_id = server.query(
        "SELECT id FROM lists WHERE room_id = ? AND name = 'Daily'", (room_id,)
    )[0][0]
    with sqlite3.connect(server.database) as connection:
        connection.execute(
            "INSERT INTO items (name, done, list_id, active_tags, description, quantity) VALUES (?, 0, ?, '[]', '', 1)",
            ("Added while this device was offline", list_id),
        )
    server.start()
    member.context.set_offline(False)
    member.wait_for_function("navigator.onLine === true", timeout=5000)
    member.evaluate("window.dispatchEvent(new Event('online'))")
    expect(
        member.get_by_text("Added while this device was offline", exact=True)
    ).to_be_visible()
    expect(
        member.get_by_text("Online check complete · read only", exact=True)
    ).to_be_visible()

    # An empty authorized room is a complete replacement, not a skipped save.
    room_id = server.query("SELECT id FROM rooms WHERE slug = ?", (room_slug,))[0][0]
    with sqlite3.connect(server.database) as connection:
        connection.execute(
            "DELETE FROM items WHERE list_id IN (SELECT id FROM lists WHERE room_id = ?)",
            (room_id,),
        )
        connection.execute("DELETE FROM lists WHERE room_id = ?", (room_id,))
    member.goto(room_url)
    expect(
        member.get_by_role("button", name="Add New List", exact=True)
    ).to_be_visible()
    member.wait_for_function(
        """async (slug) => {
            const record = await window.ListROfflineStorage.readRecord();
            return record?.snapshot.room.slug === slug && record.snapshot.lists.length === 0;
        }""",
        arg=room_slug,
        timeout=15_000,
    )
    server.stop()
    member.context.set_offline(True)
    member.goto(room_url, timeout=15_000)
    expect(member.get_by_text("Offline · read only", exact=True)).to_be_visible()
    expect(member.get_by_text("Checked apples", exact=True)).to_have_count(0)

    # Clearing the record in this disposable context demonstrates the no-copy state.
    member.evaluate(
        f"window.ListROfflineStorage.clearRecordForRoom({json.dumps(room_slug)})"
    )
    member.context.set_offline(True)
    member.goto(server.url, timeout=15_000)
    expect(
        member.get_by_text(
            re.compile("No offline copy is ready on this device"), exact=False
        )
    ).to_be_visible()


@pytest.mark.parametrize("browser", ["chromium", "firefox"], indirect=True)
@pytest.mark.parametrize("change", ["revoked", "deleted"])
def test_online_denial_clears_matching_offline_copy(server, sessions, change):
    member, _visitor = sessions
    room_slug, _list_slug, _name = prepare_snapshot_data(server)
    room_url = f"{server.url}/room/{room_slug}"
    member.goto(room_url)
    member.get_by_label("Room Password", exact=True).fill(server.password)
    member.get_by_role("button", name="Enter", exact=True).click()
    expect(member.get_by_role("button", name="Add New List")).to_be_visible()
    assert offline_record(member, room_slug)["snapshot"]["lists"]

    with sqlite3.connect(server.database) as connection:
        if change == "revoked":
            connection.execute(
                "UPDATE rooms SET authorization_version = authorization_version + 1 WHERE slug = ?",
                (room_slug,),
            )
        else:
            connection.execute("DELETE FROM rooms WHERE slug = ?", (room_slug,))

    member.goto(room_url)
    if change == "revoked":
        expect(member.get_by_label("Room Password", exact=True)).to_be_visible()
    else:
        expect(member.get_by_text("Room not found", exact=True)).to_be_visible()
    member.wait_for_function(
        "async () => (await window.ListROfflineStorage.readRecord()) === null",
        timeout=15_000,
    )
    server.stop()
    member.context.set_offline(True)
    member.goto(room_url, timeout=15_000)
    expect(
        member.get_by_text("No offline copy is ready on this device.", exact=False)
    ).to_be_visible()
    expect(member.get_by_text("Checked apples", exact=True)).to_have_count(0)


@pytest.mark.parametrize("browser", ["chromium", "firefox"], indirect=True)
def test_room_delete_clears_copy_without_offline_client_loaded(server, sessions):
    member, _visitor = sessions
    room_slug, _list_slug, _name = prepare_snapshot_data(server)
    room_url = f"{server.url}/room/{room_slug}"
    member.goto(room_url)
    member.get_by_label("Room Password", exact=True).fill(server.password)
    member.get_by_role("button", name="Enter", exact=True).click()
    expect(member.get_by_role("button", name="Add New List")).to_be_visible()
    assert offline_record(member, room_slug)["snapshot"]["lists"]

    member.goto(f"{room_url}?admin=true")
    expect(member.get_by_role("button", name="Add New List")).to_be_visible()
    assert member.evaluate("Boolean(window.ListROfflineStorage)") is False
    member.get_by_role("button", name="Room menu").click()
    member.get_by_text("Delete Room", exact=True).click()
    member.get_by_label("Enter Room Password to Confirm").fill(server.password)
    member.get_by_role("button", name="Delete", exact=True).click()
    member.wait_for_url(server.url + "/")
    member.goto(room_url)
    expect(member.get_by_text("Room not found", exact=True)).to_be_visible()
    member.wait_for_function(
        "async () => (await window.ListROfflineStorage.readRecord()) === null",
        timeout=15_000,
    )


@pytest.mark.parametrize("browser", ["chromium", "firefox"], indirect=True)
def test_temporary_snapshot_error_keeps_old_copy_and_timestamp(server, sessions):
    member, _visitor = sessions
    room_slug, _list_slug, _name = prepare_snapshot_data(server)
    room_url = f"{server.url}/room/{room_slug}"
    member.goto(room_url)
    member.get_by_label("Room Password", exact=True).fill(server.password)
    member.get_by_role("button", name="Enter", exact=True).click()
    expect(member.get_by_role("button", name="Add New List")).to_be_visible()
    old_saved_at = offline_record(member, room_slug)["saved_at"]
    endpoint = re.compile(r"/api/offline/rooms/.*/snapshot$")
    member.route(endpoint, lambda route: route.fulfill(status=503, body="unavailable"))
    member.reload()
    expect(
        member.get_by_text("The offline copy could not be updated.", exact=False)
    ).to_be_visible()
    record = member.evaluate("window.ListROfflineStorage.readRecord()")
    assert record["saved_at"] == old_saved_at
    assert "Checked apples" in json.dumps(record)
    expect(member.get_by_text("Last saved:", exact=False)).to_be_visible()
    member.unroute(endpoint)
    server.stop()
    member.context.set_offline(True)
    member.goto(room_url, timeout=15_000)
    expect(member.get_by_text("Offline · read only", exact=True)).to_be_visible()
    expect(member.get_by_text("Checked apples", exact=True)).to_be_visible()
