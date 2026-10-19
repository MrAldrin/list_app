"""Tap areas are at least 44 px tall (the touch size) on the list page.

The height is measured with hit tests, not only with the box: a small control
with a larger tap area (a pseudo-element) counts with that area, and a control
that another control covers counts less.
"""

from playwright.sync_api import Locator, expect
from svelte_app import PHONE, add_item, create_list, sign_in

TOUCH = 44

# The tap height of an element: the run of points, half a pixel apart and up
# to 40 px from its middle, that reach the element (or one inside it).
TAP_HEIGHT = """(element) => {
  const box = element.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const middle = box.top + box.height / 2;
  const reaches = (y) => {
    const hit = document.elementFromPoint(x, y);
    return hit !== null && element.contains(hit);
  };
  let top = middle;
  let bottom = middle;
  while (top - 0.5 >= middle - 40 && reaches(top - 0.5)) top -= 0.5;
  while (bottom + 0.5 <= middle + 40 && reaches(bottom + 0.5)) bottom += 0.5;
  return bottom - top + 0.5;
}"""


def assert_tap_height(name: str, locator: Locator) -> None:
    expect(locator.first).to_be_visible()
    for element in locator.all():
        element.scroll_into_view_if_needed()
        height = element.evaluate(TAP_HEIGHT)
        assert height >= TOUCH, f"{name} is {height} px tall, needs {TOUCH}"


def test_list_page_tap_areas_are_44px_tall(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    for name in ("milk", "bread"):
        add_item(page, name)

    # Options: two tags, a tag on one item, quantities, hide-done with a count.
    page.get_by_role("button", name="Options").click()
    tag_field = page.get_by_label("Add Tag")
    for tag in ("Lidl", "Market"):
        tag_field.fill(tag)
        page.get_by_role("button", name="Add new tag").click()
        expect(tag_field).to_have_value("")
    page.get_by_role("button", name="Lidl tag for milk").click()
    page.get_by_role("switch", name="Show quantities").click()
    page.get_by_role("switch", name="Hide checked-off items").click()
    page.locator(".modes label", has_text="After X days").click()
    expect(page.locator("input.count")).to_be_visible()

    assert_tap_height("row checkbox", page.locator("ul.items .check"))
    assert_tap_height("item name", page.locator("ul.items .name"))
    assert_tap_height("quantity button", page.locator("ul.items .qty button"))
    assert_tap_height("tag letter", page.locator("ul.items .tag"))
    assert_tap_height("item delete", page.locator("ul.items .delete"))
    assert_tap_height("tag filter chip", page.locator("ul.chips .chip"))
    assert_tap_height("tag remove", page.locator("ul.chips .remove"))
    assert_tap_height(
        "options row", page.locator("section[aria-label='Options'] > label")
    )
    assert_tap_height("hide mode", page.locator(".modes label"))
    assert_tap_height("days field", page.locator("input.count"))
    assert_tap_height("sort select", page.get_by_role("combobox", name="Sort"))

    # A check shows a toast with "Undo" and a dismiss button.
    page.get_by_role("checkbox", name="milk").click()
    expect(page.get_by_role("button", name="Undo")).to_be_visible()
    assert_tap_height("toast undo", page.get_by_role("button", name="Undo"))
    assert_tap_height("toast dismiss", page.get_by_role("button", name="Dismiss"))
