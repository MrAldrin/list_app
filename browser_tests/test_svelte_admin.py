"""Svelte admin page: sign in with the app password, the room overview,
create a room and reset a room password. Admin never opens a room by itself.
"""

import re

import pytest
from playwright.sync_api import expect
from svelte_app import ADMIN_PHONE, PHONE, admin_sign_in, app_url, sign_in

RESET_PASSWORD = "an-admin-reset-password"


def test_admin_sign_in_rooms_create_and_reset(svelte_server, open_session):
    server = svelte_server
    slug = server.room_slug
    owner = open_session("admin", **ADMIN_PHONE)
    member = open_session("member", **PHONE)
    sign_in(member, server)

    # The start page leads to the admin sign-in; a wrong password is refused.
    owner.goto(app_url(server))
    owner.get_by_role("button", name="Admin").click()
    expect(owner).to_have_url(re.compile(r"/admin$"))
    owner.get_by_label("Admin Password").fill("wrong")
    owner.get_by_role("button", name="Log in").click()
    expect(owner.get_by_role("alert")).to_have_text("Wrong password")
    expect(owner.get_by_label("Admin Password")).to_have_value("")
    admin_sign_in(owner, server)
    expect(owner.get_by_role("link", name="Home")).to_be_visible()

    # NiceGUI's sign-in address leads to the same page, still signed in.
    owner.goto(f"{server.url}/admin/login")
    expect(owner).to_have_url(re.compile(r"/admin$"))
    expect(owner.get_by_role("link", name="Home")).to_be_visible()

    # A room name opens the room page, which still asks for the room password.
    owner.goto(app_url(server, "admin"))
    owner.get_by_role("link", name="Home").click()
    expect(owner).to_have_url(re.compile(rf"/room/{slug}\?admin=true$"))
    expect(owner.get_by_label("Room Password")).to_be_visible()

    # Create a room: a blank name is refused, then the room opens.
    owner.goto(app_url(server, "admin"))
    owner.get_by_role("button", name="Create New Room").click()
    owner.get_by_label("Room name").fill("  ")
    owner.get_by_label("Password", exact=True).fill("cabin-pw")
    owner.get_by_role("dialog").get_by_role("button", name="Create").click()
    expect(owner.get_by_text("Room name cannot be empty")).to_be_visible()
    owner.get_by_label("Room name").fill("Cabin")
    owner.get_by_label("Password", exact=True).fill("cabin-pw")
    owner.get_by_label("Password", exact=True).press("Enter")
    expect(owner.get_by_text("Room created")).to_be_visible()
    expect(owner).to_have_url(re.compile(r"/room/cabin-[0-9a-f]{6}\?admin=true$"))
    assert server.query("SELECT name FROM rooms ORDER BY name") == [
        ("Cabin",),
        ("Home",),
    ]
    # Admin sign-in is not room access.
    owner.get_by_label("Room Password").fill("cabin-pw")
    owner.get_by_label("Room Password").press("Enter")
    expect(owner.get_by_role("button", name="Add New List")).to_be_visible()
    owner.get_by_role("link", name="Back to admin").click()
    expect(owner).to_have_url(re.compile(r"/admin$"))
    expect(owner.get_by_role("link")).to_have_text(["Cabin", "Home"])

    # Reset the Home password: blank is refused; then the member must sign in again.
    reset_button = owner.get_by_role("button", name="Reset password of Home")
    expect(reset_button).to_contain_text("Reset password")
    reset_button.click()
    dialog = owner.get_by_role("dialog", name="Admin reset of room password: Home")
    # The dialog says what happens: members are logged out, share links stay.
    expect(dialog).to_contain_text("logged out on every device")
    expect(dialog).to_contain_text("Share links to its lists keep working")
    dialog.get_by_role("button", name="Reset", exact=True).click()
    expect(owner.get_by_text("New password cannot be empty")).to_be_visible()
    expect(dialog).to_be_visible()
    dialog.get_by_label("New Room Password").fill(RESET_PASSWORD)
    dialog.get_by_role("button", name="Reset", exact=True).click()
    expect(owner.get_by_text("Password reset successfully")).to_be_visible()
    expect(owner.get_by_role("dialog")).to_have_count(0)

    expect(member.get_by_label("Room Password")).to_be_visible()
    member.get_by_label("Room Password").fill(server.password)
    member.get_by_label("Room Password").press("Enter")
    expect(member.get_by_role("alert")).to_have_text("Wrong room or password.")
    member.get_by_label("Room Password").fill(RESET_PASSWORD)
    member.get_by_label("Room Password").press("Enter")
    expect(member.get_by_role("button", name="Add New List")).to_be_visible()

    # Opened without ?admin=true: the room still asks for its password.
    owner.goto(app_url(server, f"room/{slug}"))
    expect(owner.get_by_label("Room Password")).to_be_visible()

    # Log out: the sign-in prompt comes back, also after a reload.
    owner.goto(app_url(server, "admin"))
    owner.get_by_role("button", name="Log out").click()
    expect(owner.get_by_label("Admin Password")).to_be_visible()
    owner.reload()
    expect(owner.get_by_label("Admin Password")).to_be_visible()


@pytest.mark.skip(
    reason="Retired in 4.3/4.4: tests the NiceGUI admin page; step 4.2 moved Svelte to / and NiceGUI's pages are no longer reachable"
)
def test_nicegui_admin_sign_in_does_not_carry_over_and_never_opens_a_room(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("admin", **ADMIN_PHONE)
    page.goto(f"{server.url}/admin/login")
    page.get_by_label("Admin Password").fill(server.password)
    page.get_by_role("button", name="Log in").click()
    expect(page).to_have_url(re.compile(r"/admin$"))

    page.goto(app_url(server, "admin"))
    expect(page.get_by_label("Admin Password")).to_be_visible()
    page.goto(app_url(server, f"room/{server.room_slug}?admin=true"))
    expect(page.get_by_label("Room Password")).to_be_visible()
    expect(page.get_by_role("link", name="Back to admin")).to_have_count(0)
