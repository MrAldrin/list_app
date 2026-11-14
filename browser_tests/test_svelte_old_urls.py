"""Old addresses keep working after Svelte moved from /app/ to /.

The earlier app's page shapes (`/room/{slug}`, `/list/{slug}`, `/share/{token}`,
`/create-room/{token}`, `/admin`, `/admin/login`) and the `/app/...` addresses
of the phone-testing time all open the Svelte app.
"""

from playwright.sync_api import expect
from svelte_app import PHONE, create_list, sign_in

from conftest import wait_for_api_idle


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
