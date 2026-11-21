"""The bottom bar: "Add or Search" on the list page and "Add New List" on the
room page sit at the bottom of a phone screen, within thumb reach.
"""

import re

import pytest
from playwright.sync_api import Locator, Page, expect
from svelte_app import (
    PHONE,
    add_item,
    api_seed,
    api_sign_in,
    create_list,
    open_list,
    sign_in,
)


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


@pytest.mark.all_engines
def test_add_controls_sit_at_the_bottom_and_suggestions_open_upwards(
    svelte_server, open_session
):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    expect(page.locator('meta[name="viewport"]')).to_have_attribute(
        "content", re.compile(r"\bviewport-fit=cover\b")
    )
    # These engines have no physical cutout. The bar still needs a bottom gap.
    expect(page.locator(".bottom-bar")).to_have_css("padding-bottom", "12px")
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


def test_controls_clear_simulated_screen_cutouts(svelte_server, open_session) -> None:
    width, height = 480, 320
    top, right, bottom, left = 24, 88, 34, 112
    page = open_session("cutout", viewport={"width": width, "height": height})
    # Chromium lets us supply env(safe-area-inset-*) values without a phone.
    # Use different values on each side and leave a narrow area for menus.
    cdp = page.context.new_cdp_session(page)
    cdp.send(
        "Emulation.setSafeAreaInsetsOverride",
        {"insets": {"top": top, "right": right, "bottom": bottom, "left": left}},
    )

    def assert_clear(locator: Locator) -> None:
        expect(locator).to_be_visible()
        box = box_of(locator)
        assert box["x"] >= left, box
        assert box["x"] + box["width"] <= width - right, box
        assert box["y"] >= top, box
        assert box["y"] + box["height"] <= height - bottom, box

    sign_in(page, svelte_server)
    switcher = page.get_by_role("button", name=re.compile(r"^Switch room"))
    switcher.click()
    expect(switcher).to_have_attribute("aria-expanded", "true")
    menu = page.locator("[popover]:popover-open")
    assert_clear(menu)
    page.keyboard.press("Escape")

    room_menu = page.get_by_role("button", name="Room menu")
    room_menu.click()
    expect(room_menu).to_have_attribute("aria-expanded", "true")
    assert_clear(menu)
    logout = menu.get_by_role("button", name="Log out")
    logout.scroll_into_view_if_needed()
    expect(logout).to_be_in_viewport(ratio=1)
    assert_clear(logout)
    page.keyboard.press("Escape")

    add_list = page.get_by_role("button", name="Add New List")
    assert_clear(add_list)
    add_list.click()
    assert_clear(page.get_by_role("dialog", name="New List"))
    page.keyboard.press("Escape")

    url = api_seed(
        page, svelte_server, {"Groceries": [f"item {i}" for i in range(20)]}
    )["Groceries"]
    open_list(page, url, "Groceries")
    bar = page.locator(".bottom-bar")
    expect(bar).to_have_css("padding-bottom", "34px")
    assert_clear(page.get_by_role("combobox", name="Add or Search"))
    assert_clear(page.get_by_role("button", name="Add", exact=True))
    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
    assert page.evaluate("window.scrollY") > 0
    assert_clear(page.locator("header.bar"))
    assert box_of(page.locator(".connection"))["y"] >= top
    list_menu = page.get_by_role("button", name="List menu")
    list_menu.click()
    expect(list_menu).to_have_attribute("aria-expanded", "true")
    assert_clear(menu)
    page.keyboard.press("Escape")

    add_item(page, "eggs")
    toast = page.locator(".toast").filter(has_text="Added eggs")
    assert_clear(toast)
    toast.get_by_role("button", name="Dismiss").click()
    expect(toast).to_have_count(0)

    # Deleting the test room returns to a page without a bar. Its toast
    # clears only the screen inset; it must not keep the old bar height.
    page.get_by_role("link", name="Back to room").click()
    page.get_by_role("button", name="Room menu").click()
    page.get_by_role("button", name="Delete Room").click()
    page.get_by_label("Enter Room Password to Confirm").fill(svelte_server.password)
    page.get_by_role("dialog").get_by_role("button", name="Delete").click()
    expect(bar).to_have_count(0)
    toast = page.locator(".toast").filter(has_text="Room deleted")
    assert_clear(toast)
    expect(page.locator(".toasts")).to_have_css("bottom", f"{bottom + 8}px")


def test_bottom_bar_ignores_overscroll_but_lifts_for_keyboard(
    svelte_server, open_session
) -> None:
    page = open_session("phone", **PHONE)
    # A desktop browser cannot open the phone keyboard or rubber-band like iOS.
    # Simulate the viewport reports but check the actual bar's CSS position.
    page.add_init_script("""(() => {
        const viewport = Object.assign(new EventTarget(), { offsetTop: 0, covered: 0 });
        Object.defineProperty(viewport, 'height', { get: () => window.innerHeight - viewport.covered });
        Object.defineProperty(window, 'visualViewport', { value: viewport });
    })();""")
    api_sign_in(page, svelte_server)
    open_list(
        page,
        api_seed(page, svelte_server, {"Groceries": ["milk"]})["Groceries"],
        "Groceries",
    )
    bar = page.locator(".bottom-bar")
    expect(bar).to_have_css("bottom", "0px")

    page.evaluate("""() => {
        visualViewport.offsetTop = -357;
        visualViewport.dispatchEvent(new Event('scroll'));
    }""")
    expect(bar).to_have_css("bottom", "0px")

    field = page.get_by_role("combobox", name="Add or Search")
    field.focus()
    page.evaluate("""() => {
        visualViewport.offsetTop = 0;
        visualViewport.covered = 300;
        visualViewport.dispatchEvent(new Event('resize'));
    }""")
    expect(bar).to_have_css("bottom", "300px")
    field.blur()
    expect(bar).to_have_css("bottom", "0px")
