"""Svelte creation invitations: the admin issues and revokes a link; anyone with
the link creates a room and then signs in with its password. An invitation
never opens a room by itself.
"""

import re

from playwright.sync_api import expect
from svelte_app import ADMIN_PHONE, PHONE, admin_sign_in, app_url

INVALID = "This invitation is invalid or no longer active."


def issue_invitation(page, server) -> str:
    """Generate an invitation on the admin page; return its link."""
    page.goto(app_url(server, "admin"))
    admin_sign_in(page, server)
    page.get_by_role("button", name="Generate 7-day invitation").click()
    dialog = page.get_by_role("dialog", name=re.compile(r"^Invitation #\d+$"))
    expect(dialog).to_be_visible()
    expect(dialog.get_by_text("It is only shown once")).to_be_visible()
    link = dialog.get_by_label("Invitation link").input_value()
    assert re.fullmatch(rf"{re.escape(server.url)}/create-room/[\w-]{{43,}}", link)
    dialog.get_by_role("button", name="Close").click()
    expect(page.get_by_role("dialog")).to_have_count(0)
    return link


def fill_form(page, name: str, password: str, confirmation: str | None = None):
    page.get_by_label("Room name").fill(name)
    page.get_by_label("Room password").fill(password)
    page.get_by_label("Confirm password").fill(
        password if confirmation is None else confirmation
    )


def test_issue_create_room_and_revoke(svelte_server, open_session):
    server = svelte_server
    owner = open_session("admin", **ADMIN_PHONE)
    visitor = open_session("visitor", **PHONE)
    late = open_session("late", **PHONE)

    link = issue_invitation(owner, server)
    invitation_id = int(
        server.query("SELECT id FROM room_invitations ORDER BY id DESC")[0][0]
    )
    entry = owner.get_by_role("listitem").filter(
        has_text=f"Invitation #{invitation_id}: Active"
    )
    expect(entry).to_be_visible()
    expect(
        entry.get_by_text(re.compile(r"^Created \d{4}-\d\d-\d\d \d\d:\d\d UTC$"))
    ).to_be_visible()
    expect(
        entry.get_by_text(re.compile(r"^Expires \d{4}-\d\d-\d\d \d\d:\d\d UTC$"))
    ).to_be_visible()
    # The token itself is never stored, only its hash.
    token = link.rsplit("/", 1)[1]
    assert server.query(
        "SELECT COUNT(*) FROM room_invitations WHERE token_hash = ?", (token,)
    ) == [(0,)]

    # A visitor without any sign-in opens the link. Mismatched passwords
    # create nothing.
    visitor.goto(link)
    expect(visitor.get_by_role("heading", name="Create your room")).to_be_visible()
    fill_form(visitor, "Beach", "beach-pw", "other-pw")
    visitor.get_by_role("button", name="Create room").click()
    expect(visitor.get_by_text("Passwords do not match")).to_be_visible()
    assert server.query("SELECT COUNT(*) FROM rooms") == [(1,)]

    # A blank name shows NiceGUI's message.
    fill_form(visitor, "  ", "beach-pw")
    visitor.get_by_role("button", name="Create room").click()
    expect(
        visitor.get_by_text("Room name must contain 1-100 characters.")
    ).to_be_visible()

    # Create the room: the room page asks for its password, never opens it.
    fill_form(visitor, "Beach", "beach-pw")
    visitor.get_by_label("Confirm password").press("Enter")
    expect(visitor).to_have_url(re.compile(r"/room/[\w-]+$"))
    expect(visitor.get_by_label("Room Password")).to_be_visible()
    slug = visitor.url.rsplit("/", 1)[1]
    assert server.query("SELECT name FROM rooms WHERE slug = ?", (slug,)) == [
        ("Beach",)
    ]
    visitor.get_by_label("Room Password").fill("beach-pw")
    visitor.get_by_label("Room Password").press("Enter")
    expect(visitor.get_by_role("button", name="Add New List")).to_be_visible()

    # The new room shows in the admin overview after a refresh.
    owner.get_by_role("button", name="Refresh rooms").click()
    expect(owner.get_by_role("link", name="Beach")).to_be_visible()

    # Someone opens the link, then the admin revokes it before they submit.
    late.goto(link)
    fill_form(late, "Late", "late-pw")
    owner.get_by_role("button", name=f"Revoke invitation #{invitation_id}").click()
    expect(
        owner.get_by_role("listitem").filter(
            has_text=f"Invitation #{invitation_id}: Revoked"
        )
    ).to_be_visible()
    expect(owner.get_by_role("button", name=re.compile("^Revoke"))).to_have_count(0)

    late.get_by_role("button", name="Create room").click()
    expect(late.get_by_text(INVALID)).to_be_visible()
    expect(late.get_by_role("button", name="Create room")).to_be_disabled()
    assert server.query("SELECT COUNT(*) FROM rooms WHERE name = 'Late'") == [(0,)]

    # Reopening the link shows the message and no form; the room created
    # with it keeps working.
    late.reload()
    expect(late.get_by_text(INVALID)).to_be_visible()
    expect(late.get_by_text("Ask the app admin for a new invitation.")).to_be_visible()
    expect(late.get_by_label("Room name")).to_have_count(0)
    visitor.reload()
    expect(visitor.get_by_role("button", name="Add New List")).to_be_visible()


def test_unknown_link_and_no_admin_controls_without_sign_in(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("visitor", **PHONE)

    page.goto(app_url(server, "create-room/not-a-real-token"))
    expect(page.get_by_text(INVALID)).to_be_visible()
    expect(page.get_by_role("button", name="Create room")).to_have_count(0)

    page.goto(app_url(server, "admin"))
    expect(page.get_by_label("Admin Password")).to_be_visible()
    expect(page.get_by_text("Room invitations")).to_have_count(0)


def test_a_svelte_invitation_works_in_nicegui(svelte_server, open_session):
    """Both UIs share the invitations: NiceGUI's page accepts a Svelte link."""
    server = svelte_server
    owner = open_session("admin", **ADMIN_PHONE)
    link = issue_invitation(owner, server)
    token = link.rsplit("/", 1)[1]

    visitor = open_session("visitor", **PHONE)
    visitor.goto(f"{server.url}/create-room/{token}")
    expect(visitor.get_by_text("Create your room")).to_be_visible()
    expect(visitor.get_by_label("Room name")).to_be_visible()
