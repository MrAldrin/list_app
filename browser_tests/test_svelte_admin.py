"""Svelte admin page: sign in with the app password, the room overview,
create a room and reset a room password. Admin never opens a room by itself.
"""

import re

from playwright.sync_api import expect
from svelte_app import PHONE, app_url, sign_in

RESET_PASSWORD = "an-admin-reset-password"

# NiceGUI pages install a service worker that forwards page loads. Playwright's
# WebKit then sends those loads without cookies, so NiceGUI's middleware starts
# a new session and the admin sign-in seems gone. Block service workers here:
# these tests visit NiceGUI's /admin, and Svelte has no service worker yet.
ADMIN_PHONE = {**PHONE, "service_workers": "block"}


def admin_sign_in(page, server) -> None:
    page.get_by_label("Admin Password").fill(server.password)
    page.get_by_role("button", name="Log in").click()
    expect(page.get_by_role("button", name="Create New Room")).to_be_visible()


def test_admin_sign_in_rooms_create_and_reset(svelte_server, open_session):
    server = svelte_server
    slug = server.room_slug
    owner = open_session("admin", **ADMIN_PHONE)
    member = open_session("member", **PHONE)
    sign_in(member, server)

    # The start page leads to the admin sign-in; a wrong password is refused.
    owner.goto(app_url(server))
    owner.get_by_role("button", name="Admin").click()
    expect(owner).to_have_url(re.compile(r"/app/admin$"))
    owner.get_by_label("Admin Password").fill("wrong")
    owner.get_by_role("button", name="Log in").click()
    expect(owner.get_by_role("alert")).to_have_text("Wrong password")
    expect(owner.get_by_label("Admin Password")).to_have_value("")
    admin_sign_in(owner, server)
    expect(owner.get_by_role("link", name="Home")).to_be_visible()

    # The sign-in is NiceGUI's: its admin page opens in the same browser.
    owner.goto(f"{server.url}/admin")
    expect(owner).to_have_url(re.compile(r"/admin$"))
    expect(owner.get_by_text("Refresh rooms")).to_be_visible()

    # A room name opens the room page, which still asks for the room password.
    owner.goto(app_url(server, "admin"))
    owner.get_by_role("link", name="Home").click()
    expect(owner).to_have_url(re.compile(rf"/app/room/{slug}\?admin=true$"))
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
    expect(owner).to_have_url(re.compile(r"/app/room/cabin-[0-9a-f]{6}\?admin=true$"))
    assert server.query("SELECT name FROM rooms ORDER BY name") == [
        ("Cabin",),
        ("Home",),
    ]
    # Admin sign-in is not room access.
    owner.get_by_label("Room Password").fill("cabin-pw")
    owner.get_by_label("Room Password").press("Enter")
    expect(owner.get_by_role("button", name="Add New List")).to_be_visible()
    owner.get_by_role("link", name="Back to admin").click()
    expect(owner).to_have_url(re.compile(r"/app/admin$"))
    expect(owner.get_by_role("link")).to_have_text(["Cabin", "Home"])

    # Reset the Home password: blank is refused; then the member must sign in again.
    owner.get_by_role("button", name="Reset password of Home").click()
    dialog = owner.get_by_role("dialog", name="Admin Reset: Home")
    dialog.get_by_role("button", name="Reset").click()
    expect(owner.get_by_text("New password cannot be empty")).to_be_visible()
    expect(dialog).to_be_visible()
    dialog.get_by_label("New Room Password").fill(RESET_PASSWORD)
    dialog.get_by_role("button", name="Reset").click()
    expect(owner.get_by_text("Password reset successfully")).to_be_visible()
    expect(owner.get_by_role("dialog")).to_have_count(0)

    expect(member.get_by_label("Room Password")).to_be_visible()
    member.get_by_label("Room Password").fill(server.password)
    member.get_by_label("Room Password").press("Enter")
    expect(member.get_by_role("alert")).to_have_text("Wrong room or password.")
    member.get_by_label("Room Password").fill(RESET_PASSWORD)
    member.get_by_label("Room Password").press("Enter")
    expect(member.get_by_role("button", name="Add New List")).to_be_visible()

    # A room opened without ?admin=true has no way back to admin.
    owner.goto(app_url(server, f"room/{slug}"))
    expect(owner.get_by_label("Room Password")).to_be_visible()

    # Log out: the sign-in prompt comes back, here and in NiceGUI.
    owner.goto(app_url(server, "admin"))
    owner.get_by_role("button", name="Log out").click()
    expect(owner.get_by_label("Admin Password")).to_be_visible()
    owner.reload()
    expect(owner.get_by_label("Admin Password")).to_be_visible()
    owner.goto(f"{server.url}/admin")
    expect(owner).to_have_url(re.compile(r"/admin/login$"))


def test_nicegui_admin_sign_in_carries_over_and_never_opens_a_room(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("admin", **ADMIN_PHONE)
    page.goto(f"{server.url}/admin/login")
    page.get_by_label("Admin Password").fill(server.password)
    page.get_by_role("button", name="Log in").click()
    expect(page).to_have_url(re.compile(r"/admin$"))

    page.goto(app_url(server, "admin"))
    expect(page.get_by_role("link", name="Home")).to_be_visible()
    page.goto(app_url(server, f"room/{server.room_slug}?admin=true"))
    expect(page.get_by_label("Room Password")).to_be_visible()
    expect(page.get_by_role("link", name="Back to admin")).to_have_count(0)
