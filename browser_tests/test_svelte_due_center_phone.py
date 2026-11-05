"""Phone layout and hidden reminder entry points in the shipped due views."""

import re

import pytest
from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, room_app_url, share_link, sign_in
from test_svelte_due_center import BELL, _days, _set_date
from test_svelte_share import without_share_sheet


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_phone_bell_rows_and_hidden_settings(svelte_server, open_session, theme):
    page = without_share_sheet(open_session("owner", **PHONE, color_scheme=theme))
    sign_in(page, svelte_server)
    page.get_by_role("button", name="Room menu").click()
    expect(
        page.get_by_role("button", name="Personal reminders", exact=True)
    ).to_have_count(0)
    expect(
        page.get_by_role("button", name="Personal room reminder policy")
    ).to_have_count(0)
    page.get_by_role("button", name="Room menu").click()

    create_list(page, "Groceries")
    name = "Fresh milk and breakfast cereal"
    add_item(page, name)
    _set_date(page, name, _days(-1))
    page.get_by_role("button", name="Options").click()
    expect(page.get_by_role("button", name="Personal list reminders")).to_have_count(0)
    page.get_by_role("button", name="Done", exact=True).click()
    page.get_by_role("button", name=re.compile("^Fresh milk")).click()
    dialog = page.get_by_role("dialog", name="Edit Item")
    expect(
        dialog.get_by_role("button", name="Personal reminders for this item")
    ).to_have_count(0)
    dialog.get_by_label("Due time (optional)").fill("09:00")
    dialog.get_by_role("button", name="Save", exact=True).click()
    expect(dialog).to_be_hidden()
    page.get_by_role("button", name=re.compile("^Fresh milk")).click()
    expect(dialog.get_by_label("Due time (optional)")).to_have_value("09:00")
    dialog.get_by_role("button", name="Cancel").click()
    link = share_link(page)

    page.goto(room_app_url(svelte_server))
    bell = page.get_by_role("button", name=BELL)
    bell.focus()
    page.keyboard.press("Enter")
    panel = page.get_by_role("dialog", name="Due items")
    row = panel.locator(".due-row", has_text=name)
    expect(row).to_be_visible()
    expect(
        panel.get_by_role("button", name=re.compile("reminder (settings|policy)", re.I))
    ).to_have_count(0)
    expect(row.locator(".where")).to_have_text("Groceries")
    expect(row.locator(".when")).not_to_be_empty()
    expect(row.locator(".tag")).not_to_be_empty()
    geometry = row.evaluate("""row => {
        const box = el => el.getBoundingClientRect();
        const name = box(row.querySelector('.name'));
        const metadata = ['.where', '.when', '.tag'].map(s => box(row.querySelector(s)));
        const link = box(row);
        const style = getComputedStyle(row.querySelector('.name'));
        return {name: {top: name.top, bottom: name.bottom, height: name.height},
          metadata: metadata.map(r => ({top: r.top, right: r.right, bottom: r.bottom})),
          link: {left: link.left, right: link.right, width: link.width, height: link.height},
          lineHeight: parseFloat(style.lineHeight), viewport: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth};
    }""")
    assert geometry["name"]["height"] <= geometry["lineHeight"] * 1.5
    assert all(m["top"] >= geometry["name"]["bottom"] - 1 for m in geometry["metadata"])
    assert (
        max(m["top"] for m in geometry["metadata"])
        - min(m["top"] for m in geometry["metadata"])
        <= 2
    )
    assert geometry["link"]["width"] >= 44 and geometry["link"]["height"] >= 44
    assert (
        geometry["link"]["left"] >= 0
        and geometry["link"]["right"] <= geometry["viewport"]
    )
    assert all(m["right"] <= geometry["viewport"] for m in geometry["metadata"])
    assert geometry["scrollWidth"] <= geometry["viewport"]
    page.keyboard.press("Escape")
    expect(bell).to_be_focused()
    bell.press("Enter")
    row.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("button", name=re.compile("^Fresh milk"))).to_be_focused()

    visitor = open_session("visitor", **PHONE, color_scheme=theme)
    visitor.goto(link)
    expect(visitor.get_by_role("heading", name="Groceries")).to_be_visible()
    expect(visitor.get_by_role("button", name="Room menu")).to_have_count(0)
    visitor.get_by_role("button", name=BELL).click()
    shared = visitor.get_by_role("dialog", name="Due items")
    expect(shared.locator(".due-row", has_text=name)).to_be_visible()
    expect(
        shared.get_by_role(
            "button", name=re.compile("reminder (settings|policy)", re.I)
        )
    ).to_have_count(0)
