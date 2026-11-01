"""Named room item groups, their autocomplete and their public-share boundary."""

from playwright.sync_api import expect
from svelte_app import (
    PHONE,
    add_item,
    create_list,
    item_names,
    share_link,
    sign_in,
    wait_until,
)


def open_options(page):
    page.get_by_role("button", name="Options", exact=True).click()


def add_typed_group_item(editor, name):
    field = editor.get_by_role("combobox", name="Add item name")
    field.fill(name)
    field.press("Enter")


def test_room_member_creates_reuses_and_deletes_an_item_group(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("member", **PHONE, color_scheme="light")
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_item(page, "bread")
    page.get_by_role("checkbox", name="bread").check()

    # The editor suggestions use items in other lists of this same room.
    page.get_by_role("link", name="Back to room").click()
    create_list(page, "Pantry")
    add_item(page, "coffee")
    page.get_by_role("link", name="Back to room").click()
    page.get_by_role("link", name="Groceries").click()
    expect(page.get_by_role("button", name="Item groups", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Breakfast", exact=True)).to_have_count(0)

    open_options(page)
    item_groups = page.get_by_role("button", name="Item groups", exact=True)
    expect(item_groups).to_have_css("min-height", "44px")
    item_groups.click()
    groups = page.get_by_role("dialog", name="Item groups")
    groups.get_by_role("button", name="Manage groups").click()
    groups = page.get_by_role("dialog", name="Item groups")
    groups.get_by_role("button", name="New group").click()
    editor = page.get_by_role("dialog", name="New item group")
    editor.get_by_label("Group name").fill("Breakfast")
    editor.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_role("button", name="Item groups", exact=True)).to_be_visible()
    assert server.query("SELECT name, items_json FROM item_groups") == [
        ("Breakfast", "[]")
    ]

    page.get_by_role("button", name="Item groups", exact=True).click()
    groups = page.get_by_role("dialog", name="Item groups")
    group_add = groups.get_by_role("button", name="Breakfast, empty group", exact=True)
    expect(group_add).to_be_visible()
    expect(group_add).to_have_css("min-height", "44px")
    expect(groups.get_by_role("button", name="Manage groups")).to_have_css(
        "min-height", "44px"
    )
    group_add.click()
    expect(page.get_by_text("No items to add", exact=True)).to_be_visible()
    expect(item_names(page)).to_have_text(["milk", "bread"])

    page.get_by_role("button", name="Manage groups").click()
    groups = page.get_by_role("dialog", name="Item groups")
    expect(groups.get_by_text("Empty group", exact=True)).to_be_visible()
    groups.get_by_role("button", name="Edit").click()
    editor = page.get_by_role("dialog", name="Edit 'Breakfast'")
    field = editor.get_by_role("combobox", name="Add item name")

    field.fill("cof")
    expect(
        editor.get_by_role("listbox", name="Existing items in this room")
    ).to_be_visible()
    expect(editor.get_by_role("option", name="coffee", exact=True)).to_be_visible()
    field.press("ArrowDown")
    field.press("Enter")
    expect(
        editor.get_by_role("list", name="Items in group").locator("li span")
    ).to_have_text(["coffee"])

    field.fill("br")
    expect(editor.get_by_role("option", name="bread", exact=True)).to_be_visible()
    editor.get_by_role("option", name="bread", exact=True).click()
    add_typed_group_item(editor, "eggs")
    remove_coffee = editor.get_by_role("button", name="Remove coffee")
    expect(remove_coffee).to_have_css("min-height", "44px")
    remove_coffee.click()
    field.fill("mi")
    expect(editor.get_by_role("option", name="milk", exact=True)).to_be_visible()
    field.press("ArrowDown")
    field.press("Enter")
    expect(
        editor.get_by_role("list", name="Items in group").locator("li span")
    ).to_have_text(["bread", "eggs", "milk"])

    editor.get_by_role("button", name="Save", exact=True).click()
    item_groups = page.get_by_role("button", name="Item groups", exact=True)
    expect(item_groups).to_be_visible()
    assert server.query("SELECT name, items_json FROM item_groups") == [
        ("Breakfast", '["bread", "eggs", "milk"]')
    ]

    item_groups.click()
    page.get_by_role("dialog", name="Item groups").get_by_role(
        "button", name="Breakfast", exact=True
    ).click()
    expect(page.get_by_text("Added 1; skipped 2 already on the list")).to_be_visible()
    expect(page.get_by_role("checkbox", name="bread")).to_be_checked()
    expect(page.get_by_role("checkbox", name="milk")).not_to_be_checked()
    expect(item_names(page)).to_have_text(["eggs", "milk", "bread"])
    groceries_uid = server.query("SELECT uid FROM lists WHERE name = 'Groceries'")[0][0]
    assert server.query(
        "SELECT items.name, items.done FROM items JOIN lists ON lists.id = items.list_id "
        "WHERE lists.uid = ? ORDER BY items.name COLLATE NOCASE",
        (groceries_uid,),
    ) == [("bread", 1), ("eggs", 0), ("milk", 0)]

    page.get_by_role("button", name="Manage groups").click()
    groups = page.get_by_role("dialog", name="Item groups")
    delete = groups.get_by_role("button", name="Delete", exact=True)
    expect(delete).to_have_css("color", "rgb(198, 40, 40)")
    delete.click()
    confirmation = page.get_by_role("dialog", name="Delete 'Breakfast'?")
    confirmation.get_by_role("button", name="Delete group").click()
    expect(page.get_by_role("button", name="Breakfast", exact=True)).to_have_count(0)
    assert server.query(
        "SELECT items.name FROM items JOIN lists ON lists.id = items.list_id "
        "WHERE lists.uid = ? ORDER BY items.name COLLATE NOCASE",
        (groceries_uid,),
    ) == [
        ("bread",),
        ("eggs",),
        ("milk",),
    ]
    page.get_by_role("dialog", name="Item groups").get_by_role(
        "button", name="Close"
    ).click()
    page.get_by_role("button", name="Done", exact=True).click()
    expect(page.get_by_role("button", name="Manage groups")).to_have_count(0)
    expect(page.get_by_role("button", name="Breakfast", exact=True)).to_have_count(0)


def test_stale_group_edit_keeps_the_draft_until_explicit_overwrite(
    svelte_server, open_session
):
    server = svelte_server
    first = open_session("first", **PHONE)
    second = open_session("second", **PHONE)
    sign_in(first, server)
    sign_in(second, server)
    list_url = create_list(first, "Groceries")
    open_options(first)
    first.get_by_role("button", name="Item groups", exact=True).click()
    first.get_by_role("dialog", name="Item groups").get_by_role(
        "button", name="Manage groups"
    ).click()
    first.get_by_role("dialog", name="Item groups").get_by_role(
        "button", name="New group"
    ).click()
    editor = first.get_by_role("dialog", name="New item group")
    editor.get_by_label("Group name").fill("Original")
    add_typed_group_item(editor, "milk")
    editor.get_by_role("button", name="Save", exact=True).click()

    second.goto(list_url)
    expect(second.get_by_role("button", name="Original", exact=True)).to_have_count(0)
    open_options(second)
    expect(second.get_by_role("button", name="Item groups", exact=True)).to_be_visible()
    for page in (first, second):
        page.get_by_role("button", name="Item groups", exact=True).click()
        page.get_by_role("dialog", name="Item groups").get_by_role(
            "button", name="Manage groups"
        ).click()
        page.get_by_role("dialog", name="Item groups").get_by_role(
            "button", name="Edit"
        ).click()
    first_editor = first.get_by_role("dialog", name="Edit 'Original'")
    second_editor = second.get_by_role("dialog", name="Edit 'Original'")
    first_editor.get_by_label("Group name").fill("My draft")
    add_typed_group_item(first_editor, "draft item")
    second_editor.get_by_label("Group name").fill("Saved elsewhere")
    add_typed_group_item(second_editor, "latest item")
    second_editor.get_by_role("button", name="Save", exact=True).click()

    with first.expect_response(
        lambda response: (
            response.request.method == "PUT" and "/item-groups/" in response.url
        )
    ) as stale_response:
        first_editor.get_by_role("button", name="Save", exact=True).click()
    assert stale_response.value.status == 409
    expect(first.get_by_role("alert")).to_contain_text(
        "Someone else changed this group"
    )
    expect(first_editor.get_by_label("Group name")).to_have_value("My draft")
    expect(
        first_editor.get_by_role("list", name="Items in group").locator("li span")
    ).to_have_text(["milk", "draft item"])
    overwrite = first_editor.get_by_label("Save my draft over the latest version")
    expect(overwrite).not_to_be_checked()
    save_mine = first_editor.get_by_role("button", name="Save my draft")
    expect(save_mine).to_be_disabled()
    overwrite.check()
    save_mine.click()

    expect(first.get_by_role("button", name="Item groups", exact=True)).to_be_visible()
    assert server.query("SELECT name, items_json FROM item_groups") == [
        ("My draft", '["milk", "draft item"]')
    ]


def test_saved_group_can_still_add_items_offline_from_options(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("offline-groups", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")

    open_options(page)
    page.get_by_role("button", name="Item groups", exact=True).click()
    page.get_by_role("dialog", name="Item groups").get_by_role(
        "button", name="Manage groups"
    ).click()
    page.get_by_role("dialog", name="Item groups").get_by_role(
        "button", name="New group"
    ).click()
    editor = page.get_by_role("dialog", name="New item group")
    editor.get_by_label("Group name").fill("Breakfast")
    add_typed_group_item(editor, "oats")
    editor.get_by_role("button", name="Save", exact=True).click()
    page.get_by_role("button", name="Item groups", exact=True).click()
    groups = page.get_by_role("dialog", name="Item groups")
    expect(groups.get_by_role("button", name="Breakfast", exact=True)).to_be_visible()
    groups.get_by_role("button", name="Close").click()

    server.stop()
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_be_visible()
    page.get_by_role("button", name="Done", exact=True).click()
    open_options(page)
    page.get_by_role("button", name="Item groups", exact=True).click()
    groups = page.get_by_role("dialog", name="Item groups")
    group = groups.get_by_role("button", name="Breakfast", exact=True)
    expect(group).to_be_enabled()
    expect(groups.get_by_role("button", name="Manage groups")).to_be_disabled()
    group.click()
    expect(page.get_by_text("queued 1 for sync", exact=False)).to_be_visible()
    expect(item_names(page)).to_have_text(["milk", "oats"])
    groups.get_by_role("button", name="Close").click()
    assert server.query("SELECT name FROM items ORDER BY name") == [("milk",)]

    server.start()
    page.evaluate("window.dispatchEvent(new Event('online'))")
    expect(page.get_by_text("Offline — changes are saved", exact=False)).to_have_count(
        0, timeout=30_000
    )
    wait_until(
        page,
        lambda: (
            server.query("SELECT name FROM items ORDER BY name")
            == [("milk",), ("oats",)]
        ),
        "the offline group add did not reach the server",
        timeout_ms=20_000,
    )


def test_public_share_does_not_expose_room_item_groups(svelte_server, open_session):
    server = svelte_server
    member = open_session("member", **PHONE)
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    open_options(member)
    member.get_by_role("button", name="Item groups", exact=True).click()
    groups = member.get_by_role("dialog", name="Item groups")
    groups.get_by_role("button", name="Manage groups").click()
    groups = member.get_by_role("dialog", name="Item groups")
    groups.get_by_role("button", name="New group").click()
    editor = member.get_by_role("dialog", name="New item group")
    editor.get_by_label("Group name").fill("Private group")
    add_typed_group_item(editor, "milk")
    editor.get_by_role("button", name="Save", exact=True).click()

    link = share_link(member)
    responses = []
    visitor.on(
        "response",
        lambda response: (
            responses.append(response.json())
            if "/share/" in response.url and "/changes" in response.url
            else None
        ),
    )
    visitor.goto(link)
    expect(visitor.get_by_role("heading", name="Groceries")).to_be_visible()
    visitor.get_by_role("button", name="Options", exact=True).click()
    expect(visitor.get_by_role("button", name="Item groups", exact=True)).to_have_count(
        0
    )
    assert server.query("SELECT name FROM item_groups") == [("Private group",)]
    assert responses and all(response.get("groups") == [] for response in responses)
