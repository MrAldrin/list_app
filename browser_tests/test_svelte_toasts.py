"""Svelte toasts stay small and inside the screen.

At Gate A the real iPhone showed a toast as tall as the screen; no test had
checked the toast size. These checks measure the toasts on a phone screen,
also when several are stacked, with a long message, above an open dialog and
on a short (landscape) screen.
"""

import struct
import zlib

from playwright.sync_api import Page, expect
from svelte_app import PHONE, add_item, create_list, sign_in

# One line of text with the 2rem buttons; well under two lines.
MAX_TOAST_HEIGHT = 48


def png_pixel(png: bytes) -> tuple[int, int, int]:
    """The color of a one-pixel PNG screenshot."""
    chunks, offset = [], 8
    while offset < len(png):
        (length,) = struct.unpack(">I", png[offset : offset + 4])
        kind = png[offset + 4 : offset + 8]
        chunks.append((kind, png[offset + 8 : offset + 8 + length]))
        offset += length + 12
    header = dict(chunks)[b"IHDR"]
    assert header[8] == 8 and header[9] in (2, 6), header  # 8-bit RGB or RGBA
    data = zlib.decompress(b"".join(c for kind, c in chunks if kind == b"IDAT"))
    # Byte 0 is the row filter. For the first pixel of the first row every
    # filter predicts 0, so the bytes are the color itself.
    return data[1], data[2], data[3]


def toast_boxes(page: Page) -> list[dict]:
    return [box for box in (t.bounding_box() for t in toasts(page).all()) if box]


def toasts(page: Page):
    return page.locator(".toasts .toast")


def expect_small_and_on_screen(page: Page, count: int = 1) -> None:
    """Measure the toasts on screen; at least `count` of them.

    Toasts go after 4 s, so the test waits for a count, not an exact one.
    """
    expect(toasts(page).nth(count - 1)).to_be_visible()
    viewport = page.viewport_size
    assert viewport
    boxes = toast_boxes(page)
    assert len(boxes) >= count
    for box in boxes:
        assert box["height"] <= MAX_TOAST_HEIGHT, box
        assert box["x"] >= 0, box
        assert box["y"] >= 0, box
        assert box["x"] + box["width"] <= viewport["width"], box
        assert box["y"] + box["height"] <= viewport["height"], box
    # Stacked toasts sit together at the bottom; the area is no taller than them.
    area = page.locator(".toasts").bounding_box()
    assert area
    top = min(box["y"] for box in boxes)
    bottom = max(box["y"] + box["height"] for box in boxes)
    assert area["height"] <= bottom - top + 1, (area, boxes)
    assert bottom > viewport["height"] - 3 * MAX_TOAST_HEIGHT, (bottom, viewport)


def test_toasts_are_small_and_inside_the_screen(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    expect(page.get_by_text("List created")).to_be_visible()
    expect_small_and_on_screen(page)

    # A long message stays on one line and ends in "…".
    long_name = "very long item name " * 12
    add_item(page, long_name)
    message = toasts(page).filter(has_text="Added very long").locator("span")
    expect(message).to_be_visible()
    assert message.evaluate("span => span.scrollWidth > span.clientWidth")
    expect_small_and_on_screen(page)

    # Three toasts (the most at once) stack at the bottom, each still small.
    add_item(page, "milk")
    add_item(page, "bread")
    add_item(page, "apples")
    expect_small_and_on_screen(page, 3)

    # Above an open dialog (the toast area joins the browser's top layer).
    expect(toasts(page)).to_have_count(0)
    page.get_by_role("button", name="milk", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Item Name").fill("bread")
    dialog.get_by_role("button", name="Save").click()
    expect(page.get_by_text("'bread' already exists")).to_be_visible()
    expect(dialog).to_be_visible()
    expect_small_and_on_screen(page)
    # A modal dialog makes the rest of the page inert, so the browser's hit
    # test never finds the toast. Compare a painted pixel with its color.
    toast = toasts(page).first
    box = toast.bounding_box()
    assert box
    color = toast.evaluate("element => getComputedStyle(element).backgroundColor")
    pixel = page.screenshot(
        clip={
            "x": box["x"] + 4,
            "y": box["y"] + box["height"] / 2,
            "width": 1,
            "height": 1,
        }
    )
    assert f"rgb{png_pixel(pixel)}".replace(" ", "") == color.replace(" ", ""), (
        "The toast must be painted above the open dialog"
    )
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()

    # A short, wide screen (a phone on its side).
    page.set_viewport_size({"width": 844, "height": 390})
    add_item(page, "eggs")
    expect_small_and_on_screen(page)
