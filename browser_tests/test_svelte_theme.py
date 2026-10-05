"""Svelte light and dark mode: NiceGUI's "Toggle dark mode" button.

Without a saved choice the page follows the phone or computer. The button
saves the choice in this browser under NiceGUI's key, so both UIs share it.
"""

import pytest
from playwright.sync_api import Page, expect
from svelte_app import PHONE, app_url, create_list, sign_in

DARK_BACKGROUND = "rgb(17, 20, 24)"
LIGHT_BACKGROUND = "rgb(244, 245, 247)"


def toggle(page: Page):
    return page.get_by_role("button", name="Toggle dark mode")


def expect_theme(page: Page, theme: str) -> None:
    expect(page.locator("html")).to_have_attribute("data-theme", theme)
    background = DARK_BACKGROUND if theme == "dark" else LIGHT_BACKGROUND
    expect(page.locator("body")).to_have_css("background-color", background)
    color = "#111418" if theme == "dark" else "#f4f5f7"
    expect(page.locator('meta[name="theme-color"]')).to_have_attribute("content", color)
    expect(toggle(page)).to_have_attribute(
        "aria-pressed", "true" if theme == "dark" else "false"
    )


def saved(page: Page) -> str | None:
    return page.evaluate("localStorage.getItem('listapp_theme')")


def test_theme_follows_the_system_until_toggled(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE, color_scheme="dark")

    # No choice saved: the system's dark mode. The start page has no top
    # bar, so the button sits above the page.
    page.goto(app_url(server))
    expect(toggle(page)).to_have_count(1)
    expect_theme(page, "dark")
    assert saved(page) is None

    toggle(page).click()
    expect_theme(page, "light")
    assert saved(page) == "light"

    # The room and list pages show the button in their top bar, once.
    sign_in(page, server)
    expect(
        page.locator("header").get_by_role("button", name="Toggle dark mode")
    ).to_be_visible()
    expect(toggle(page)).to_have_count(1)
    expect_theme(page, "light")
    page.reload()
    expect(page.get_by_role("button", name="Add New List")).to_be_visible()
    expect_theme(page, "light")

    create_list(page, "Theme")
    expect(toggle(page)).to_have_count(1)
    toggle(page).click()
    expect_theme(page, "dark")
    assert saved(page) == "dark"

    # A saved choice wins over the system.
    page.emulate_media(color_scheme="light")
    expect_theme(page, "dark")


def test_system_changes_apply_while_nothing_is_saved(svelte_server, open_session):
    page = open_session("phone", **PHONE, color_scheme="light")
    page.goto(app_url(svelte_server))
    expect_theme(page, "light")

    page.emulate_media(color_scheme="dark")
    expect_theme(page, "dark")
    assert saved(page) is None


def test_choice_is_shared_with_nicegui(svelte_server, open_session):
    server = svelte_server
    page = open_session("phone", **PHONE, color_scheme="light")
    page.goto(app_url(server))
    toggle(page).click()
    expect_theme(page, "dark")

    # NiceGUI's pages read the same key on the same site.
    page.goto(server.url)
    expect(page.locator("body.body--dark")).to_be_visible()

    # And the other way round.
    page.get_by_role("button", name="Toggle dark mode").click()
    expect(page.locator("body.body--light")).to_be_visible()
    page.goto(app_url(server))
    expect_theme(page, "light")


def test_other_browsers_keep_their_own_choice(svelte_server, open_session):
    first = open_session("first", **PHONE, color_scheme="light")
    second = open_session("second", **PHONE, color_scheme="light")
    first.goto(app_url(svelte_server))
    toggle(first).click()
    expect_theme(first, "dark")

    second.goto(app_url(svelte_server))
    expect_theme(second, "light")
    assert saved(second) is None


@pytest.mark.parametrize(
    ("choice", "background"), [("dark", DARK_BACKGROUND), ("light", LIGHT_BACKGROUND)]
)
def test_saved_theme_paints_before_the_app_scripts(
    svelte_server, browser, choice, background
):
    # The app's scripts are blocked: only app.html's inline script runs, so
    # the first paint already has the saved colors.
    context = browser.new_context(
        **PHONE, color_scheme="dark" if choice == "light" else "light"
    )
    context.add_init_script(f"localStorage.setItem('listapp_theme', '{choice}')")
    context.route(
        "**/*",
        lambda route: (
            route.abort()
            if route.request.resource_type == "script"
            else route.continue_()
        ),
    )
    try:
        page = context.new_page()
        page.goto(app_url(svelte_server), wait_until="load")
        assert page.evaluate("document.documentElement.dataset.theme") == choice
        assert (
            page.evaluate("getComputedStyle(document.body).backgroundColor")
            == background
        )
    finally:
        context.close()
