"""Svelte share links: view and edit a list by its link, reset the link.

The Svelte versions of `test_public_sharing.py`: a visitor without the room
password opens the link, edits the list and never gets into the room. A reset
stops the old link at once, also for an edit or undo the visitor sends after
it.
"""

import json
import re

from playwright.sync_api import Page, expect
from svelte_app import PHONE, add_item, app_url, create_list, item_names, sign_in

SHARE_LINK = re.compile(r"/share/[A-Za-z0-9_-]{43}$")
RESET_MESSAGE = "This list was deleted or this share link was reset."
UNAVAILABLE_MESSAGE = "This list was deleted or you no longer have access."


def without_share_sheet(page: Page) -> Page:
    """Hide the phone share sheet, so the link dialog shows on every engine."""
    page.context.add_init_script("delete Navigator.prototype.share")
    return page


def share_link(page: Page) -> str:
    page.get_by_role("button", name="List menu").click()
    page.get_by_role("button", name="Share List").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Share this list")).to_be_visible()
    expect(
        dialog.get_by_text("Anyone with this link can open this list.")
    ).to_be_visible()
    link = dialog.get_by_role("textbox", name="Link").input_value()
    assert SHARE_LINK.search(link), link
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_have_count(0)
    return link


def reset_link(page: Page) -> None:
    page.get_by_role("button", name="List menu").click()
    page.get_by_role("button", name="Reset share link").click()
    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Reset share link?")).to_be_visible()
    expect(
        dialog.get_by_text(
            "Everyone using the old link will lose access. Room access stays unchanged."
        )
    ).to_be_visible()
    dialog.get_by_role("button", name="Reset share link").click()
    expect(page.get_by_text("Share link reset", exact=True)).to_be_visible()
    expect(dialog).to_have_count(0)


def hold_live_updates(page: Page) -> None:
    """The visitor's live stream never connects, so it misses the reset.

    Its next write is then sent with the old link, as from a phone that was
    asleep while the link was reset.
    """
    page.route("**/api/v1/share/*/events", lambda route: None)


def share_token(server) -> str:
    return server.query("SELECT share_token FROM lists WHERE name = 'Groceries'")[0][0]


def test_visitor_views_and_edits_by_link_and_reset_stops_it(
    svelte_server, open_session
):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = without_share_sheet(open_session("visitor", **PHONE))
    sign_in(member, server)
    list_url = create_list(member, "Groceries")
    add_item(member, "milk")

    link = share_link(member)
    assert link.endswith(f"/share/{share_token(server)}")

    # The visitor sees and edits the list, both ways live.
    visitor.goto(link)
    expect(visitor.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(item_names(visitor)).to_have_text(["milk"])
    expect(visitor.get_by_role("link", name="Back to room")).to_have_count(0)
    visitor.get_by_role("button", name="List menu").click()
    expect(visitor.get_by_role("button", name="Share List")).to_be_visible()
    expect(visitor.get_by_role("button", name="Reset share link")).to_have_count(0)
    visitor.keyboard.press("Escape")
    add_item(visitor, "bread")
    expect(item_names(member)).to_have_text(["bread", "milk"])
    add_item(member, "eggs")
    expect(item_names(visitor)).to_have_text(["bread", "eggs", "milk"])

    # Tags too, as on NiceGUI's public page.
    visitor.get_by_role("button", name="Options").click()
    visitor.get_by_label("Add Tag").fill("produce")
    visitor.get_by_label("Add Tag").press("Enter")
    expect(
        visitor.get_by_role("list", name="Tags").get_by_role(
            "button", name="produce", exact=True
        )
    ).to_be_visible()
    assert json.loads(
        server.query("SELECT list_tags FROM lists WHERE name = 'Groceries'")[0][0]
    ) == ["produce"]

    # The visitor shares the same link.
    assert share_link(visitor) == link

    # Cancel keeps the link.
    member.get_by_role("button", name="List menu").click()
    member.get_by_role("button", name="Reset share link").click()
    member.get_by_role("dialog").get_by_role("button", name="Cancel").click()
    assert share_link(member) == link

    # Reset: the open visitor page learns it at once.
    reset_link(member)
    expect(visitor.get_by_text(RESET_MESSAGE)).to_be_visible()
    expect(item_names(visitor)).to_have_count(0)
    expect(visitor.get_by_label("Add or Search")).to_have_count(0)
    visitor.goto(link)
    expect(visitor.get_by_text(UNAVAILABLE_MESSAGE)).to_be_visible()
    expect(visitor.get_by_text("milk")).to_have_count(0)

    # The new link works; the member keeps room access.
    new_link = share_link(member)
    assert new_link != link
    visitor.goto(new_link)
    add_item(visitor, "apples")
    expect(item_names(member)).to_have_text(["apples", "bread", "eggs", "milk"])
    assert member.url == list_url

    # A share link never opens the room.
    visitor.goto(app_url(server, f"room/{server.room_slug}"))
    expect(visitor.get_by_label("Room Password")).to_be_visible()
    expect(visitor.get_by_role("link", name="Groceries")).to_have_count(0)


def test_writes_sent_after_a_reset_change_nothing(svelte_server, open_session):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    add_item(member, "undo target")
    link = share_link(member)

    # Undo of a delete, after the reset.
    hold_live_updates(visitor)
    visitor.goto(link)
    visitor.get_by_role("button", name="Options").click()
    visitor.get_by_role("button", name="Delete undo target").click()
    expect(visitor.get_by_text("Deleted undo target")).to_be_visible()
    expect(item_names(member)).to_have_count(0)
    reset_link(member)
    with visitor.expect_response(re.compile(r"/api/v1/share/.*/ops$")) as answer:
        visitor.get_by_role("button", name="Undo").click()
    assert answer.value.status == 401
    expect(visitor.get_by_text(RESET_MESSAGE)).to_be_visible()
    assert server.query("SELECT name FROM items") == []

    # A new item, after the next reset.
    second = open_session("second visitor", **PHONE)
    hold_live_updates(second)
    second.goto(share_link(member))
    second.get_by_label("Add or Search").fill("forbidden add")
    reset_link(member)
    with second.expect_response(re.compile(r"/api/v1/share/.*/ops$")) as answer:
        second.get_by_label("Add or Search").press("Enter")
    assert answer.value.status == 401
    expect(second.get_by_text(RESET_MESSAGE)).to_be_visible()
    assert server.query("SELECT name FROM items") == []

    # Room access is unchanged.
    add_item(member, "room still works")
    assert server.query("SELECT name FROM items") == [("room still works",)]


def test_invalid_links_show_no_list(svelte_server, open_session):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    add_item(member, "private contents")
    link = share_link(member)
    list_slug = server.query("SELECT slug FROM lists WHERE name = 'Groceries'")[0][0]

    for invalid in (link[:-1], app_url(server, f"share/{'x' * 43}"), list_slug):
        url = (
            invalid
            if invalid.startswith("http")
            else app_url(server, f"share/{invalid}")
        )
        visitor.goto(url)
        expect(visitor.get_by_text(UNAVAILABLE_MESSAGE)).to_be_visible()
        expect(visitor.get_by_text("private contents")).to_have_count(0)
        expect(visitor.get_by_label("Add or Search")).to_have_count(0)


def test_room_menu_shares_the_room_link(svelte_server, open_session):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    sign_in(member, server)
    member.get_by_role("button", name="Room menu").click()
    member.get_by_role("button", name="Share Room").click()
    dialog = member.get_by_role("dialog")
    expect(dialog.get_by_role("heading", name="Share this room")).to_be_visible()
    expect(
        dialog.get_by_text("The recipient will also need the room password.")
    ).to_be_visible()
    expect(dialog.get_by_role("textbox", name="Link")).to_have_value(
        app_url(server, f"room/{server.room_slug}")
    )
    dialog.get_by_role("button", name="Close").click()
    expect(dialog).to_have_count(0)


def test_visitor_edits_tags_but_cannot_rename_or_delete_the_list(
    svelte_server, open_session
):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    list_url = create_list(member, "Groceries")
    add_item(member, "milk")
    link = share_link(member)

    # The room's own list address asks a visitor for the room password.
    visitor.goto(list_url)
    expect(visitor.get_by_label("Room Password")).to_be_visible()
    expect(visitor.get_by_text("milk")).to_have_count(0)

    # By the link: tags can be added and deleted.
    visitor.goto(link)
    visitor.get_by_role("button", name="Options").click()
    visitor.get_by_label("Add Tag").fill("produce")
    visitor.get_by_label("Add Tag").press("Enter")
    tags = visitor.get_by_role("list", name="Tags")
    expect(tags.get_by_role("button", name="produce", exact=True)).to_be_visible()
    assert json.loads(server.query("SELECT list_tags FROM lists")[0][0]) == ["produce"]
    with visitor.expect_response(re.compile(r"/api/v1/share/.*/ops$")) as answer:
        visitor.get_by_role("button", name="Delete tag produce").click()
    assert answer.value.ok
    expect(visitor.get_by_text("Deleted tag produce")).to_be_visible()
    expect(tags.get_by_role("button", name="produce", exact=True)).to_have_count(0)
    assert json.loads(server.query("SELECT list_tags FROM lists")[0][0]) == []

    # No rename or delete of the list, and no reset of the link.
    expect(visitor.get_by_role("button", name=re.compile("^Rename"))).to_have_count(0)
    expect(visitor.get_by_label("List Name")).to_have_count(0)
    expect(
        visitor.get_by_role("button", name=re.compile("^Delete Groceries"))
    ).to_have_count(0)
    visitor.get_by_role("button", name="List menu").click()
    expect(visitor.get_by_role("button", name="Share List")).to_be_visible()
    expect(visitor.get_by_role("button", name="Reset share link")).to_have_count(0)
    assert server.query("SELECT name FROM lists") == [("Groceries",)]


def test_edits_and_tags_sent_after_a_reset_change_nothing(svelte_server, open_session):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    sign_in(member, server)
    create_list(member, "Groceries")
    add_item(member, "milk")

    # An item edit from a dialog that was open during the reset.
    editor = open_session("editor", **PHONE)
    hold_live_updates(editor)
    editor.goto(share_link(member))
    editor.get_by_role("button", name="milk", exact=True).click()
    editor.get_by_role("dialog").get_by_label("Item Name").fill("forbidden edit")
    reset_link(member)
    with editor.expect_response(re.compile(r"/api/v1/share/.*/ops$")) as answer:
        editor.get_by_role("dialog").get_by_role("button", name="Save").click()
    assert answer.value.status == 401
    expect(editor.get_by_text(RESET_MESSAGE)).to_be_visible()
    assert server.query("SELECT name FROM items") == [("milk",)]

    # A new tag typed before the next reset and sent after it.
    tagger = open_session("tagger", **PHONE)
    hold_live_updates(tagger)
    tagger.goto(share_link(member))
    tagger.get_by_role("button", name="Options").click()
    tagger.get_by_label("Add Tag").fill("revoked tag")
    reset_link(member)
    with tagger.expect_response(re.compile(r"/api/v1/share/.*/ops$")) as answer:
        tagger.get_by_label("Add Tag").press("Enter")
    assert answer.value.status == 401
    expect(tagger.get_by_text(RESET_MESSAGE)).to_be_visible()
    assert json.loads(server.query("SELECT list_tags FROM lists")[0][0]) == []

    # The new link can add a tag.
    tagger.goto(share_link(member))
    tagger.get_by_role("button", name="Options").click()
    tagger.get_by_label("Add Tag").fill("current tag")
    tagger.get_by_label("Add Tag").press("Enter")
    expect(
        tagger.get_by_role("list", name="Tags").get_by_role(
            "button", name="current tag", exact=True
        )
    ).to_be_visible()
    assert json.loads(server.query("SELECT list_tags FROM lists")[0][0]) == [
        "current tag"
    ]


def test_a_room_member_gets_the_way_back_and_can_reset_on_the_share_page(
    svelte_server, open_session
):
    """Decision 146: as in NiceGUI, a browser with room access sees both."""
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    add_item(member, "milk")
    link = share_link(member)

    # The member opens the link: the back arrow and the reset are there.
    member.goto(link)
    expect(member.get_by_role("heading", name="Groceries")).to_be_visible()
    back = member.get_by_role("link", name="Back to room")
    expect(back).to_be_visible()
    member.get_by_role("button", name="List menu").click()
    expect(member.get_by_role("button", name="Reset share link")).to_be_visible()
    member.keyboard.press("Escape")
    back.click()
    expect(member).to_have_url(re.compile(rf"/room/{server.room_slug}$"))
    expect(member.get_by_role("link", name="Groceries")).to_be_visible()

    # Reset from the share page: the old link stops, the page follows the new one.
    visitor.goto(link)
    expect(item_names(visitor)).to_have_text(["milk"])
    member.goto(link)
    reset_link(member)
    expect(member).to_have_url(re.compile(r"/share/[A-Za-z0-9_-]{43}$"))
    assert not member.url.endswith(link.rsplit("/", 1)[1])
    assert member.url.endswith(share_token(server))
    expect(item_names(member)).to_have_text(["milk"])
    expect(member.get_by_role("link", name="Back to room")).to_be_visible()
    expect(visitor.get_by_text(RESET_MESSAGE)).to_be_visible()
    add_item(member, "bread")
    assert server.query("SELECT name FROM items ORDER BY name") == [
        ("bread",),
        ("milk",),
    ]


def test_without_room_access_the_share_page_reveals_nothing_about_the_room(
    svelte_server, open_session
):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    link = share_link(member)
    slug = server.room_slug

    def check_hidden(page: Page, seen: list[str]) -> None:
        expect(page.get_by_role("heading", name="Groceries")).to_be_visible()
        expect(page.get_by_role("link", name="Back to room")).to_have_count(0)
        page.get_by_role("button", name="List menu").click()
        expect(page.get_by_role("button", name="Share List")).to_be_visible()
        expect(page.get_by_role("button", name="Reset share link")).to_have_count(0)
        page.keyboard.press("Escape")
        assert not any(slug in page_text for page_text in seen), "room slug leaked"
        assert not any('"Home"' in page_text for page_text in seen), "room name leaked"
        assert slug not in page.content()
        assert not page.locator(f"a[href*='{slug}']").count()

    # A browser that never had the room cookie.
    bodies: list[str] = []
    visitor.on(
        "response",
        lambda response: (
            bodies.append(response.text())
            if "/api/" in response.url or response.url == link
            else None
        ),
    )
    visitor.goto(link)
    check_hidden(visitor, bodies)

    # A member whose cookie is gone (as after sign-out or a password change).
    member.context.clear_cookies()
    stale: list[str] = []
    member.on(
        "response",
        lambda response: (
            stale.append(response.text()) if "/api/" in response.url else None
        ),
    )
    member.goto(link)
    check_hidden(member, stale)
