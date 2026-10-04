"""Shared checked-item visibility settings in real browsers."""

from playwright.sync_api import expect
from test_public_sharing import add_item, create_list, share_link

expect.set_options(timeout=10_000)


def item_text(page, name):
    """List rows only; a closing suggestion menu can linger in a portal."""
    return page.locator("#app").get_by_text(name, exact=True)


def item_checkbox(page, name):
    return item_text(page, name).locator("..").get_by_role("checkbox")


def mode_button(page, name):
    return page.locator(".q-btn-toggle").get_by_role("button", name=name, exact=True)


def test_visibility_settings_modes_history_and_shared_updates(server, sessions):
    member, visitor = sessions
    private_url = create_list(member, server)
    link = share_link(member)
    add_item(member, "milk")
    item_checkbox(member, "milk").click()
    expect(item_checkbox(member, "milk")).to_be_checked()

    visitor.goto(link)
    expect(item_text(visitor, "milk")).to_be_visible()
    member.get_by_role("button", name="Options", exact=True).click()
    main_switch = member.get_by_role("switch", name="Hide checked-off items")
    expect(main_switch).not_to_be_checked()
    assert server.query(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE name = ?",
        ("Browser groceries",),
    ) == [("off", 7, 10)]

    main_switch.click()
    expect(item_text(member, "milk")).not_to_be_visible()
    expect(item_text(visitor, "milk")).not_to_be_visible()
    assert server.query(
        "SELECT hide_done_mode FROM lists WHERE name = ?", ("Browser groceries",)
    ) == [("all",)]

    # Hidden items remain searchable and Add restores the complete history row.
    search = visitor.get_by_label("Add or Search", exact=True)
    search.fill("milk")
    suggestion = visitor.locator(".q-menu .q-item").filter(has_text="milk")
    expect(suggestion).to_be_visible()
    suggestion.click()
    expect(item_text(visitor, "milk")).to_be_visible()
    expect(item_checkbox(visitor, "milk")).not_to_be_checked()

    visitor.get_by_role("button", name="Options", exact=True).click()
    mode_button(visitor, "After X days").click()
    age_input = visitor.get_by_label("Days before hiding", exact=True)
    expect(age_input).to_have_value("7")
    item_checkbox(visitor, "milk").click()
    expect(item_checkbox(visitor, "milk")).to_be_checked()
    expect(item_text(visitor, "milk")).to_be_visible()
    assert server.query(
        "SELECT hide_done_mode FROM lists WHERE name = ?", ("Browser groceries",)
    ) == [("age",)]
    expect(mode_button(member, "After X days")).to_have_attribute(
        "aria-pressed", "true"
    )

    age_input.fill("0")
    age_input.press("Tab")
    expect(item_text(visitor, "milk")).not_to_be_visible()
    expect(item_text(member, "milk")).not_to_be_visible()
    age_input = visitor.get_by_label("Days before hiding", exact=True)
    age_input.fill("1")
    age_input.press("Tab")
    expect(item_text(visitor, "milk")).to_be_visible()
    expect(item_text(member, "milk")).to_be_visible()

    mode_button(visitor, "Keep last X").click()
    expect(mode_button(member, "After X days")).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(mode_button(member, "Keep last X")).to_have_attribute("aria-pressed", "true")
    recent_input = visitor.get_by_label("Checked items to keep", exact=True)
    expect(recent_input).to_have_value("10")
    recent_input.fill("0")
    recent_input.press("Tab")
    expect(item_text(visitor, "milk")).not_to_be_visible()
    expect(item_text(member, "milk")).not_to_be_visible()

    # Turning the main switch off reveals all; re-enabling starts in all mode
    # while preserving the numeric counters.
    visitor.get_by_role("switch", name="Hide checked-off items").click()
    expect(item_text(visitor, "milk")).to_be_visible()
    visitor.get_by_role("switch", name="Hide checked-off items").click()
    expect(item_text(visitor, "milk")).not_to_be_visible()
    expect(mode_button(member, "After X days")).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(mode_button(member, "All")).to_have_attribute("aria-pressed", "true")
    assert server.query(
        "SELECT hide_done_mode, hide_done_age_days, hide_done_recent_count "
        "FROM lists WHERE name = ?",
        ("Browser groceries",),
    ) == [("all", 1, 0)]
    expect(member).to_have_url(private_url)
