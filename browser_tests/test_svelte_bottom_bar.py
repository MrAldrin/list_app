"""The bottom bar: "Add or Search" on the list page and "Add New List" on the
room page sit at the bottom of a phone screen, within thumb reach.
"""

from playwright.sync_api import Page, expect
from svelte_app import PHONE, add_item, create_list, sign_in


def box_of(locator) -> dict:
    box = locator.bounding_box()
    assert box
    return box


def assert_at_bottom(page: Page, locator) -> None:
    viewport = page.viewport_size
    assert viewport
    box = box_of(locator)
    # Inside the screen and in its lowest part.
    assert box["y"] + box["height"] <= viewport["height"], (box, viewport)
    assert box["y"] > viewport["height"] - 120, (box, viewport)


def test_add_controls_sit_at_the_bottom_and_suggestions_open_upwards(
    svelte_server, open_session
):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    assert_at_bottom(page, page.get_by_role("button", name="Add New List"))

    create_list(page, "Groceries")
    field = page.get_by_role("combobox", name="Add or Search")
    assert_at_bottom(page, field)

    # Enough rows to scroll: the last one can still scroll out from under the bar.
    for index in range(20):
        add_item(page, f"item {index:02d}")
    last = page.get_by_role("button", name="item 19", exact=True)
    last.scroll_into_view_if_needed()
    page.mouse.wheel(0, 5000)
    page.wait_for_timeout(200)
    assert (
        box_of(last)["y"] + box_of(last)["height"]
        <= box_of(page.locator(".bottom-bar"))["y"] + 1
    )
    assert_at_bottom(page, field)

    # Suggestions open above the field, not below it off the screen.
    field.fill("item 1")
    suggestions = page.get_by_role("listbox", name="Suggestions")
    expect(suggestions).to_be_visible()
    assert (
        box_of(suggestions)["y"] + box_of(suggestions)["height"] <= box_of(field)["y"]
    )
