"""Svelte: room access, share links and open pages survive a server restart.

The server restarts with the same database; the browsers keep their cookies.
An open page reconnects its live stream without a reload.
"""

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, app_url, create_list, item_names, sign_in
from test_svelte_share import share_link, without_share_sheet

# A restart takes a few seconds, and the stream retries after 1, 2 and 5 s.
RECONNECT_TIMEOUT = 30_000


def test_remembered_room_and_share_link_survive_a_restart(svelte_server, open_session):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    add_item(member, "milk")
    link = share_link(member)

    for page in (member, visitor):
        page.goto("about:blank")
    server.restart()

    # The start page still goes to the room, without the password.
    member.goto(app_url(server))
    expect(member.get_by_role("link", name="Groceries")).to_be_visible()
    expect(member.get_by_label("Room Password")).to_have_count(0)
    member.get_by_role("link", name="Groceries").click()
    expect(item_names(member)).to_have_text(["milk"])
    assert share_link(member) == link

    # The share link still works, live both ways.
    visitor.goto(link)
    add_item(visitor, "after restart")
    expect(item_names(member)).to_have_text(["after restart", "milk"])


def test_open_list_page_recovers_after_a_restart(svelte_server, open_session):
    server = svelte_server
    member = without_share_sheet(open_session("member", **PHONE))
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    list_url = create_list(member, "Groceries")
    add_item(member, "before restart")
    link = share_link(member)
    member.evaluate("window.testDocumentBeforeRestart = true")

    # The member's page stays open through the restart.
    server.restart()
    visitor.goto(link)
    expect(item_names(visitor)).to_have_text(["before restart"])
    add_item(visitor, "from visitor after restart")
    expect(item_names(member)).to_have_text(
        ["before restart", "from visitor after restart"], timeout=RECONNECT_TIMEOUT
    )
    # Same page, no reload; and it can still write.
    assert member.url == list_url
    assert member.evaluate("window.testDocumentBeforeRestart === true")
    add_item(member, "member after restart")
    expect(item_names(visitor)).to_have_count(3)
    assert server.query("SELECT name FROM items ORDER BY name") == [
        ("before restart",),
        ("from visitor after restart",),
        ("member after restart",),
    ]
