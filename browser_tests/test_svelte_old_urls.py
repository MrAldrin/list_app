"""Old addresses keep working after Svelte moved from /app/ to /.

The earlier app's page shapes (`/room/{slug}`, `/list/{slug}`, `/share/{token}`,
`/create-room/{token}`, `/admin`, `/admin/login`) and the `/app/...` addresses
of the phone-testing time all open the Svelte app.
"""

import re

from conftest import wait_for_api_idle
from playwright.sync_api import expect
from svelte_app import PHONE, create_list, sign_in
from test_svelte_invitations import issue_invitation


def test_room_and_old_list_address(svelte_server, open_session):
    server = svelte_server
    slug = server.room_slug
    page = open_session("member", **PHONE)

    page.goto(f"{server.url}/room/{slug}")
    expect(page.get_by_label("Room Password")).to_be_visible()
    sign_in(page, server)
    expect(page).to_have_url(f"{server.url}/room/{slug}")
    list_slug = create_list(page, "Groceries").rsplit("/", 1)[1]

    # NiceGUI's list address has no room: it opens the list in the last room.
    wait_for_api_idle(page)
    page.goto(f"{server.url}/list/{list_slug}")
    expect(page).to_have_url(f"{server.url}/room/{slug}/list/{list_slug}")
    expect(page.get_by_role("heading", name="Groceries")).to_be_visible()

    # The bare address goes to the last room.
    wait_for_api_idle(page)
    page.goto(f"{server.url}/")
    expect(page).to_have_url(f"{server.url}/room/{slug}")
    expect(page.get_by_role("heading", name="Home")).to_be_visible()


def test_old_share_address(svelte_server, open_session):
    server = svelte_server
    member = open_session("member", **PHONE)
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    token = server.query("SELECT share_token FROM lists WHERE name = 'Groceries'")[0][0]

    visitor.goto(f"{server.url}/share/{token}")
    expect(visitor.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(visitor.get_by_label("Add or Search")).to_be_visible()
    expect(visitor.get_by_label("Room Password")).to_have_count(0)

    # The phone-testing address redirects, and the page still works.
    visitor.goto(f"{server.url}/app/share/{token}")
    expect(visitor).to_have_url(f"{server.url}/share/{token}")
    expect(visitor.get_by_role("heading", name="Groceries")).to_be_visible()


def test_old_admin_addresses(svelte_server, open_session):
    server = svelte_server
    page = open_session("admin", **PHONE)

    page.goto(f"{server.url}/admin")
    expect(page.get_by_label("Admin Password")).to_be_visible()
    # NiceGUI's own sign-in address leads to the same page.
    page.goto(f"{server.url}/admin/login")
    expect(page).to_have_url(f"{server.url}/admin")
    expect(page.get_by_label("Admin Password")).to_be_visible()
    page.goto(f"{server.url}/app/admin")
    expect(page).to_have_url(f"{server.url}/admin")
    expect(page.get_by_label("Admin Password")).to_be_visible()


def test_old_invitation_addresses(svelte_server, open_session):
    server = svelte_server
    owner = open_session("admin", **PHONE)
    visitor = open_session("visitor", **PHONE)
    link = issue_invitation(owner, server)
    token = link.rsplit("/", 1)[1]

    visitor.goto(link)
    expect(visitor.get_by_role("heading", name="Create your room")).to_be_visible()
    visitor.goto(f"{server.url}/app/create-room/{token}")
    expect(visitor).to_have_url(f"{server.url}/create-room/{token}")
    expect(visitor.get_by_label("Room name")).to_be_visible()


def test_app_prefix_redirects_keep_the_query(svelte_server, open_session):
    server = svelte_server
    slug = server.room_slug
    page = open_session("phone", **PHONE)

    page.goto(f"{server.url}/app/room/{slug}?admin=true")
    expect(page).to_have_url(f"{server.url}/room/{slug}?admin=true")
    expect(page.get_by_label("Room Password")).to_be_visible()

    page.goto(f"{server.url}/app/")
    expect(page).to_have_url(re.compile(rf"^{re.escape(server.url)}/$"))
    expect(page.get_by_label("Room link or code")).to_be_visible()
    page.goto(f"{server.url}/app")
    expect(page).to_have_url(f"{server.url}/")


def test_server_addresses_are_not_the_page(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    response = page.request.get(f"{server.url}/api/v1/does-not-exist")
    assert response.status == 404
    assert response.headers["content-type"].startswith("application/json")
    assert (
        page.request.get(f"{server.url}/favicon.ico").headers["content-type"]
        == "image/png"
    )
    index = page.request.get(f"{server.url}/")
    assert index.headers["referrer-policy"] == "same-origin"
