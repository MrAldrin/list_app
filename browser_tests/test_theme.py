"""Theme preferences belong to the browser, not the shared room."""

import pytest
from playwright.sync_api import expect


def test_theme_is_remembered_per_browser(server, sessions):
    first, second = sessions
    first.goto(server.url)
    toggle = first.get_by_role("button", name="Toggle dark mode")
    expect(toggle).to_be_visible()
    toggle.click()
    expect(first.locator("body.body--dark")).to_be_visible()
    assert first.evaluate("localStorage.getItem('listapp_theme')") == "dark"
    assert first.evaluate("document.documentElement.dataset.listrTheme") == "dark"

    first.goto(server.room_url)
    expect(first.locator("body.body--dark")).to_be_visible()
    first.reload()
    expect(first.locator("body.body--dark")).to_be_visible()

    second.goto(server.url)
    expect(second.locator("body.body--light")).to_be_visible()
    assert second.evaluate("localStorage.getItem('listapp_theme')") is None

    first.get_by_role("button", name="Toggle dark mode").click()
    expect(first.locator("body.body--light")).to_be_visible()
    assert first.evaluate("localStorage.getItem('listapp_theme')") == "light"
    assert first.evaluate("document.documentElement.dataset.listrTheme") == "light"


@pytest.mark.parametrize(
    ("saved", "background"),
    [("dark", "rgb(18, 18, 18)"), ("light", "rgb(255, 255, 255)")],
)
def test_saved_theme_paints_before_nicegui_scripts(server, browser, saved, background):
    context = browser.new_context()
    context.add_init_script(f"localStorage.setItem('listapp_theme', '{saved}')")
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
        page.goto(server.room_url, wait_until="domcontentloaded")
        assert page.evaluate("document.documentElement.dataset.listrTheme") == saved
        assert (
            page.evaluate("getComputedStyle(document.documentElement).backgroundColor")
            == background
        )
        if saved == "dark":
            assert page.evaluate("getComputedStyle(document.body).backgroundColor") == (
                background
            )
    finally:
        context.close()
