"""Svelte accessibility basics: names for every control, keyboard focus.

Contrast is checked from app.css by `frontend/src/app-colors.test.ts`.
"""

from conftest import wait_for_api_idle
from playwright.sync_api import Page, expect
from svelte_app import (
    PHONE,
    add_item,
    admin_sign_in,
    app_url,
    create_list,
    sign_in,
)

# Visible buttons, links and fields without a name a screen reader can say.
UNNAMED_CONTROLS = """() => {
  const visible = (el) => el.checkVisibility() && el.getClientRects().length > 0;
  const named = (el) => {
    if (el.getAttribute('aria-label')?.trim()) return true;
    const ids = el.getAttribute('aria-labelledby');
    if (ids && ids.split(' ').some((id) => document.getElementById(id)?.textContent.trim()))
      return true;
    if (el.labels && [...el.labels].some((label) => label.textContent.trim())) return true;
    if (el.closest('label')?.textContent.trim()) return true;
    return Boolean(el.textContent.trim());
  };
  return [...document.querySelectorAll('button, a[href], input, textarea, select')]
    .filter((el) => el.type !== 'hidden' && visible(el) && !named(el))
    .map((el) => el.outerHTML.slice(0, 120));
}"""


def expect_all_named(page: Page) -> None:
    assert page.evaluate(UNNAMED_CONTROLS) == []


def test_every_control_has_a_name(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)

    page.goto(app_url(server))
    expect(page.get_by_label("Room link or code")).to_be_visible()
    expect_all_named(page)

    page.goto(app_url(server, f"room/{server.room_slug}"))
    expect(page.get_by_label("Room Password")).to_be_visible()
    expect_all_named(page)

    sign_in(page, server)
    expect_all_named(page)

    create_list(page, "Names")
    add_item(page, "milk")
    page.get_by_role("button", name="Options").click()
    page.get_by_label("Add Tag").fill("Shop")
    page.get_by_label("Add Tag").press("Enter")
    expect(page.get_by_role("button", name="Shop tag for milk")).to_be_visible()
    page.get_by_role("switch", name="Show quantities").check()
    page.get_by_role("switch", name="Hide checked-off items").check()
    page.get_by_text("Keep last X").click()
    expect_all_named(page)

    page.get_by_label("Add or Search").fill("mi")
    expect(page.get_by_role("option", name="milk")).to_be_visible()
    expect_all_named(page)


def test_admin_controls_have_names(svelte_server, open_session):
    page = open_session("admin", **PHONE)
    page.goto(app_url(svelte_server, "admin"))
    expect(page.get_by_label("Admin Password")).to_be_visible()
    expect_all_named(page)
    admin_sign_in(page, svelte_server)
    expect_all_named(page)


def test_focus_returns_to_the_opener_after_a_dialog(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE)
    sign_in(page, server)
    create_list(page, "Focus")
    page.go_back()

    # Saved: the page closes the dialog; the focus goes back to its button.
    rename = page.get_by_role("button", name="Rename Focus")
    # Edits stay disabled while the page revalidates access and the feed. A page
    # restored from the back/forward cache does this again, so let it finish.
    wait_for_api_idle(page)
    expect(rename).to_be_enabled()
    rename.focus()
    page.keyboard.press("Enter")
    field = page.get_by_label("List Name")
    expect(field).to_be_visible()
    field.fill("Focused")
    field.press("Enter")
    expect(field).to_be_hidden()
    expect(page.get_by_role("button", name="Rename Focused")).to_be_focused()

    # Escape: the browser gives the focus back.
    page.keyboard.press("Enter")
    expect(page.get_by_label("List Name")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_label("List Name")).to_be_hidden()
    expect(page.get_by_role("button", name="Rename Focused")).to_be_focused()


def test_hide_mode_works_with_the_keyboard(svelte_server, open_session):
    page = open_session("phone", **PHONE)
    sign_in(page, svelte_server)
    create_list(page, "Keys")
    page.get_by_role("button", name="Options").click()
    page.get_by_role("switch", name="Hide checked-off items").check()

    chosen = page.get_by_role("radio", checked=True)
    chosen.focus()
    page.keyboard.press("ArrowRight")
    expect(page.get_by_role("radio", name="After X days")).to_be_checked()
    expect(page.get_by_label("Days before hiding")).to_be_visible()
