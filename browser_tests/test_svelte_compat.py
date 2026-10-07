"""A new server version turns the page read-only and offers a reload."""

import re

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, item_names, sign_in

API_ROUTES = re.compile(r".*/api/v1/(?!.*/events).*")


def _answer_with_version(version: str):
    """A route handler that changes the version header of API answers."""

    def handler(route):
        response = route.fetch()
        route.fulfill(
            response=response, headers={**response.headers, "x-api-version": version}
        )

    return handler


def test_new_server_version_blocks_writes_until_reload(svelte_server, open_session):
    server = svelte_server
    page = open_session("compat", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    field = page.get_by_label("Add or Search")
    notice = page.get_by_role("alert").filter(has_text="A new version is available")
    expect(notice).to_have_count(0)

    # The server is replaced: its next answer names another API version.
    page.route(API_ROUTES, _answer_with_version("2"))
    add_item(page, "bread")
    expect(notice).to_be_visible()
    expect(notice.get_by_role("button", name="Reload")).to_be_visible()
    expect(item_names(page)).to_have_text(["bread", "milk"])

    # The answer that carried the new version was still a real answer, so
    # its change is on the server. Further edits are disabled.
    assert server.query("SELECT count(*) FROM items") == [(2,)]
    expect(page.get_by_role("button", name="Add", exact=True)).to_be_disabled()
    expect(page.get_by_role("checkbox", name="milk")).to_be_disabled()
    write_requests = []
    page.on(
        "request",
        lambda request: (
            write_requests.append(request.url)
            if request.method != "GET" and "/api/v1/" in request.url
            else None
        ),
    )
    field.fill("eggs")
    field.press("Enter")
    page.wait_for_timeout(500)
    assert write_requests == []
    assert server.query("SELECT count(*) FROM items") == [(2,)]

    # Nothing reloads by itself; the button does it, onto the matching server.
    page.unroute(API_ROUTES)
    with page.expect_navigation():
        notice.get_by_role("button", name="Reload").click()
    expect(item_names(page)).to_have_text(["bread", "milk"])
    expect(notice).to_have_count(0)
    expect(page.get_by_label("Add or Search")).to_be_enabled()
    add_item(page, "apples")
    expect(item_names(page)).to_have_text(["apples", "bread", "milk"])


def test_answers_without_a_version_do_not_block_anything(svelte_server, open_session):
    page = open_session("compat-missing", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")

    def without_version(route):
        response = route.fetch()
        headers = {k: v for k, v in response.headers.items() if k != "x-api-version"}
        route.fulfill(response=response, headers=headers)

    page.route(API_ROUTES, without_version)
    add_item(page, "milk")
    expect(page.get_by_role("alert")).to_have_count(0)
    add_item(page, "bread")
    expect(item_names(page)).to_have_text(["bread", "milk"])
