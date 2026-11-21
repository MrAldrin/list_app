"""Svelte toasts stay small and inside the screen.

At Gate A, the real iPhone showed a toast as tall as the screen. No test had
checked its size. These tests measure toast size on a phone with stacked
toasts, a long message, an open dialog and a short landscape screen.
"""

import struct
import zlib

import pytest
from playwright.sync_api import Page, expect
from svelte_app import (
    PHONE,
    add_item,
    api_seed,
    api_sign_in,
    create_list,
    open_list,
    sign_in,
)

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


def expect_small_and_on_screen(page: Page) -> None:
    """Check that each visible toast is small and inside the screen."""
    expect(toasts(page).first).to_be_visible()
    viewport = page.viewport_size
    assert viewport
    boxes = toast_boxes(page)
    assert 1 <= len(boxes) <= 2
    for box in boxes:
        assert box["height"] <= MAX_TOAST_HEIGHT, box
        assert box["x"] >= 0, box
        assert box["y"] >= 0, box
        assert box["x"] + box["width"] <= viewport["width"], box
        assert box["y"] + box["height"] <= viewport["height"], box
    # Stacked toasts stay together. The area is no taller than the stack.
    area = page.locator(".toasts").bounding_box()
    assert area
    top = min(box["y"] for box in boxes)
    bottom = max(box["y"] + box["height"] for box in boxes)
    assert area["height"] <= bottom - top + 1, (area, boxes)
    bar = page.locator(".bottom-bar").bounding_box()
    assert bar
    assert bar["y"] - bottom == pytest.approx(8, abs=1), (bottom, bar)
    header = page.locator("header").first.bounding_box()
    if header and page.locator("dialog[open]").count() == 0:
        assert top >= header["y"] + header["height"], (top, header)


@pytest.mark.all_engines
def test_toasts_are_small_and_inside_the_screen(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Groceries")
    expect(page.get_by_text("List created")).to_be_visible()
    expect_small_and_on_screen(page)
    expect(page.get_by_text("Share List", exact=True)).to_be_enabled()

    # A long message stays on one line and ends in "…".
    long_name = "very long item name " * 12
    add_item(page, long_name)
    message = toasts(page).filter(has_text="Added very long").locator("span")
    expect(message).to_be_visible()
    assert message.evaluate("span => span.scrollWidth > span.clientWidth")
    expect_small_and_on_screen(page)

    # At most two toasts stack at the bottom; a third pushes out the oldest.
    add_item(page, "milk")
    add_item(page, "bread")
    add_item(page, "apples")
    expect(toasts(page).locator("span")).to_have_text(["Added bread", "Added apples"])
    expect_small_and_on_screen(page)

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


@pytest.mark.all_engines
@pytest.mark.parametrize(
    ("width", "height", "pan", "keyboard"),
    [(390, 844, 38, 440), (844, 390, 20, 140)],
    ids=["portrait", "landscape"],
)
def test_toasts_stay_inside_visual_viewport_while_typing(
    svelte_server, open_session, width: int, height: int, pan: int, keyboard: int
) -> None:
    page = open_session(
        "phone", viewport={"width": width, "height": height}, has_touch=True
    )
    # The test drivers cannot open the OS keyboard. Simulate its viewport
    # reports, including a positive offsetTop when the browser pans to focus.
    page.add_init_script(f"""(() => {{
        const viewport = Object.assign(new EventTarget(), {{ offsetTop: {pan}, covered: {keyboard} }});
        Object.defineProperty(viewport, 'height', {{
            get: () => window.innerHeight - viewport.offsetTop - viewport.covered
        }});
        Object.defineProperty(window, 'visualViewport', {{ value: viewport }});
    }})();""")
    api_sign_in(page, svelte_server)
    names = ["almond", "apple", "apricot", "avocado", "bread", "milk"]
    url = api_seed(page, svelte_server, {"Groceries": names})["Groceries"]
    open_list(page, url, "Groceries")
    bar = page.locator(".bottom-bar")
    field = page.get_by_role("combobox", name="Add or Search")
    suggestions = page.get_by_role("listbox", name="Suggestions")
    area = page.locator(".toasts")

    def expect_above(anchor: str) -> None:
        page.wait_for_function(
            """anchor => {
                const target = document.querySelector(anchor)?.getBoundingClientRect();
                const area = document.querySelector('.toasts:popover-open')?.getBoundingClientRect();
                return target && area && Math.abs(target.top - area.bottom - 8) <= 1;
            }""",
            arg=anchor,
        )
        bounds = area.evaluate("""el => {
            const { top, bottom } = el.getBoundingClientRect();
            return { top, bottom, viewportTop: visualViewport.offsetTop,
                viewportBottom: visualViewport.offsetTop + visualViewport.height };
        }""")
        assert bounds["viewportTop"] <= bounds["top"], bounds
        assert bounds["bottom"] <= bounds["viewportBottom"], bounds

    add_item(page, "eggs")
    add_item(page, "corn")
    expect(toasts(page).locator("span")).to_have_text(["Added eggs", "Added corn"])
    expect(field).to_be_focused()
    expect(bar).to_have_css("bottom", f"{keyboard}px")
    expect_above(".bottom-bar")

    # The stack rises as suggestions open and grow. In landscape the popup
    # must scroll rather than pushing any toast outside the visible area.
    field.fill("apric")
    expect(suggestions.get_by_role("option")).to_have_count(1)
    expect_above(".suggestions")
    field.fill("a")
    expect(suggestions.get_by_role("option")).to_have_count(5)
    expect_above(".suggestions")
    expect(toasts(page)).to_have_count(2)
    assert suggestions.evaluate("el => el.scrollHeight > el.clientHeight")

    if width > height:
        # If only the bar and two toasts fit, the popup must not lift them.
        page.evaluate("""() => {
            const bar = document.querySelector('.bottom-bar');
            const stack = document.querySelector('.toasts');
            const visibleHeight = bar.offsetHeight + stack.offsetHeight + 8 + 2;
            visualViewport.covered = innerHeight - visualViewport.offsetTop - visibleHeight;
            visualViewport.dispatchEvent(new Event('resize'));
        }""")
        expect(field).to_have_attribute("aria-expanded", "false")
        expect(suggestions).to_be_hidden()
        expect_above(".bottom-bar")
        expect(toasts(page)).to_have_count(2)

        # With less room, only the newest toast fits. With even less, the
        # bar keeps its place and neither toast covers the add controls.
        newest = toasts(page).last.bounding_box()
        assert newest
        visible_toasts = toasts(page).filter(visible=True)

        def set_toast_room(room: float) -> None:
            page.evaluate(
                """room => {
                    const bar = document.querySelector('.bottom-bar');
                    const visibleHeight = bar.offsetHeight + 8 + room;
                    visualViewport.covered = innerHeight - visualViewport.offsetTop - visibleHeight;
                    visualViewport.dispatchEvent(new Event('resize'));
                }""",
                room,
            )

        set_toast_room(newest["height"])
        expect(visible_toasts.locator("span")).to_have_text(["Added corn"])
        expect_above(".bottom-bar")
        set_toast_room(newest["height"] - 1)
        expect(visible_toasts).to_have_count(0)
        expect(field).to_be_focused()
        assert bar.evaluate("""el => {
            const { top, bottom } = el.getBoundingClientRect();
            return top >= visualViewport.offsetTop &&
                Math.abs(bottom - visualViewport.offsetTop - visualViewport.height) <= 1;
        }""")

        # Give the popup space again. Both toasts return without losing focus or text.
        page.evaluate(
            """covered => {
            visualViewport.covered = covered;
            visualViewport.dispatchEvent(new Event('resize'));
        }""",
            keyboard,
        )
        expect(field).to_be_focused()
        expect(suggestions.get_by_role("option")).to_have_count(5)
        expect(visible_toasts.locator("span")).to_have_text(
            ["Added eggs", "Added corn"]
        )
        expect_above(".suggestions")

    field.press("Escape")
    expect(suggestions).to_be_hidden()
    expect_above(".bottom-bar")

    # Close the simulated keyboard; the first row can still take a tap.
    field.fill("")
    page.evaluate("""() => {
        visualViewport.offsetTop = visualViewport.covered = 0;
        visualViewport.dispatchEvent(new Event('resize'));
    }""")
    expect(bar).to_have_css("bottom", "0px")
    expect_above(".bottom-bar")
    first = page.get_by_role("checkbox", name="almond")
    first.tap()
    expect(first).to_be_checked()
    expect(toasts(page).filter(has_text="Added corn")).to_be_visible()


@pytest.mark.all_engines
def test_a_toast_can_be_used_while_a_dialog_is_open(svelte_server, open_session):
    """Pressing a toast's x over a dialog closes the toast, not the dialog.

    A modal dialog makes the rest of the page inert, so the toasts are shown
    inside the open dialog (decision 145). Before, a tap on the x landed on the
    backdrop and closed the dialog, which lost the typed text.
    """
    page = open_session("phone", **PHONE)
    api_sign_in(page, svelte_server)
    open_list(
        page,
        api_seed(page, svelte_server, {"Groceries": ["milk", "bread"]})["Groceries"],
        "Groceries",
    )
    expect(toasts(page)).to_have_count(0, timeout=10_000)

    page.get_by_role("button", name="milk", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Item Name").fill("bread")
    dialog.get_by_role("button", name="Save").click()
    toast = toasts(page).filter(has_text="'bread' already exists")
    expect(toast).to_be_visible()
    # The toast is part of the open dialog, so it is not inert.
    expect(dialog.locator(".toasts .toast")).to_have_count(1)
    expect(page.locator(".toasts")).to_have_count(1)
    toast.get_by_role("button", name="Dismiss").click()
    expect(toast).to_have_count(0)
    # The dialog is still open and keeps what was typed.
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Item Name")).to_have_value("bread")

    # A second toast goes by itself; the dialog stays open meanwhile.
    dialog.get_by_role("button", name="Save").click()
    expect(toast).to_be_visible()
    expect(toast).to_have_count(0, timeout=10_000)
    expect(dialog).to_be_visible()

    # After the dialog closes, new toasts show in the page again.
    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    add_item(page, "eggs")
    added = toasts(page).filter(has_text="Added eggs")
    expect(added).to_be_visible()
    expect(page.locator(".toasts")).to_have_count(1)
    added.get_by_role("button", name="Dismiss").click()
    expect(added).to_have_count(0)
