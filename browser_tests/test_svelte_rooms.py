"""Svelte start page, room login and the room page's lists, on a phone screen."""

import re

from conftest import wait_for_api_idle
from playwright.sync_api import expect
from svelte_app import PHONE, app_url, create_list, list_links, room_app_url, sign_in


def test_start_page_login_and_remembered_room(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)

    # No remembered room: the start page asks for a room link or code.
    page.goto(app_url(server))
    expect(page.get_by_text("Open your room link to continue")).to_be_visible()
    page.get_by_role("button", name="Open Room").click()
    expect(page.get_by_text("Enter a room link or code")).to_be_visible()
    page.get_by_label("Room link or code").fill(server.room_url)
    page.get_by_label("Room link or code").press("Enter")
    expect(page).to_have_url(room_app_url(server))

    # Wrong password, then the right one.
    password = page.get_by_label("Room Password")
    password.fill("wrong")
    password.press("Enter")
    expect(page.get_by_role("alert")).to_have_text("Wrong room or password.")
    expect(password).to_have_value("")
    password.fill(server.password)
    page.get_by_role("button", name="Enter").click()
    expect(page.get_by_role("heading", name="Home")).to_be_visible()
    expect(page.get_by_text("No lists yet. Create your first one!")).to_be_visible()

    # The start page now goes straight to the remembered room.
    page.goto(app_url(server))
    expect(page).to_have_url(room_app_url(server))
    expect(page.get_by_role("heading", name="Home")).to_be_visible()

    # Log out: the password prompt comes back, also after a reload.
    page.get_by_role("button", name="Room menu").click()
    # Reload only after the server sign-out answered; a reload mid-request makes
    # WebKit report the cancelled DELETE as a page error.
    with page.expect_response(
        lambda r: r.request.method == "DELETE" and r.url.endswith("/session")
    ):
        page.get_by_role("button", name="Log out").click()
    expect(page.get_by_label("Room Password")).to_be_visible()
    page.reload()
    expect(page.get_by_label("Room Password")).to_be_visible()


def test_room_page_creates_renames_and_deletes_lists(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    page.goto(room_app_url(server))
    page.get_by_label("Room Password").fill(server.password)
    page.get_by_label("Room Password").press("Enter")

    # Create opens the new list; back on the room page it is listed.
    create_list(page, "Groceries")
    expect(page.get_by_text("List created")).to_be_visible()
    page.go_back()
    expect(list_links(page)).to_have_text(["Groceries"])
    create_list(page, "apples")
    page.go_back()

    # The same name in other letter case opens the existing list, and says so.
    page.get_by_role("button", name="Add New List").click()
    page.get_by_label("List name").fill("GROCERIES")
    page.get_by_label("List name").press("Enter")
    expect(page.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(page.get_by_text("Opened existing list")).to_be_visible()
    page.go_back()
    expect(list_links(page)).to_have_text(["apples", "Groceries"])

    # Rename: a duplicate is refused and the dialog stays open.
    page.get_by_role("button", name="Rename apples").click()
    page.get_by_label("List Name").fill("groceries")
    page.get_by_label("List Name").press("Enter")
    expect(page.get_by_text("'groceries' already exists in this room")).to_be_visible()
    page.get_by_label("List Name").fill("Bakery")
    page.get_by_role("button", name="Save").click()
    expect(page.get_by_text("Updated Bakery")).to_be_visible()
    expect(list_links(page)).to_have_text(["Bakery", "Groceries"])

    # Delete asks first; Cancel keeps the list.
    page.get_by_role("button", name="Delete Bakery").click()
    expect(page.get_by_text("Delete 'Bakery' and its 0 items?")).to_be_visible()
    page.get_by_role("button", name="Cancel").click()
    expect(list_links(page)).to_have_count(2)
    page.get_by_role("button", name="Delete Bakery").click()
    page.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(page.get_by_text("Deleted 'Bakery'")).to_be_visible()
    expect(list_links(page)).to_have_text(["Groceries"])

    assert server.query("SELECT name FROM lists ORDER BY name") == [("Groceries",)]


def test_logout_shows_the_prompt_before_the_server_answers_and_retries(
    svelte_server, open_session
):
    server = svelte_server
    slug = server.room_slug
    # Playwright's WebKit ignores page.route for a page the worker controls.
    page = open_session("phone", service_workers="block", **PHONE)
    held = []
    page.route(
        re.compile(r"/api/v1/rooms/[^/]+/session$"),
        lambda route: (
            held.append(route)
            if route.request.method == "DELETE" and not held
            else route.continue_()
        ),
    )
    sign_in(page, server)
    wait_for_api_idle(page)

    # The DELETE is held: the prompt shows only because the local sign-out
    # marker is already stored, not because the server answered.
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Log out").click()
    expect(page.get_by_label("Room Password")).to_be_visible()
    for _ in range(200):  # the DELETE goes out right after the marker
        if held:
            break
        page.wait_for_timeout(25)
    assert len(held) == 1
    assert page.request.get(f"{server.url}/api/v1/rooms/{slug}/session").ok

    # The server fails the DELETE. This tab does not retry by itself, so the
    # cookie still works; the pending sign-out is retried when the room opens.
    # (Reloading while the DELETE is held would make WebKit report the
    # cancelled request as a page error.)
    held[0].fulfill(status=503)
    wait_for_api_idle(page)
    expect(page.get_by_label("Room Password")).to_be_visible()
    assert page.request.get(f"{server.url}/api/v1/rooms/{slug}/session").ok
    with page.expect_response(
        lambda r: r.request.method == "DELETE" and r.url.endswith("/session")
    ):
        page.reload()
    expect(page.get_by_label("Room Password")).to_be_visible()
    wait_for_api_idle(page)
    assert page.request.get(f"{server.url}/api/v1/rooms/{slug}/session").status == 401
