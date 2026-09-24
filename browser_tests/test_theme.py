"""Theme preferences belong to the browser, not the shared room."""

from playwright.sync_api import expect


def test_theme_is_remembered_per_browser(server, sessions):
    first, second = sessions
    first.goto(server.url)
    toggle = first.get_by_role("button", name="Toggle dark mode")
    expect(toggle).to_be_visible()
    toggle.click()
    expect(first.locator("body.body--dark")).to_be_visible()
    assert first.evaluate("localStorage.getItem('listapp_theme')") == "dark"

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
