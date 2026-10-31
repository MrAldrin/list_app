"""Named room item groups and their boundary from public list shares."""

from playwright.sync_api import expect
from svelte_app import PHONE, add_item, create_list, item_names, share_link, sign_in


def test_room_member_creates_reuses_and_deletes_an_item_group(
    svelte_server, open_session
):
    server = svelte_server
    page = open_session("member", **PHONE)
    sign_in(page, server)
    create_list(page, "Groceries")
    add_item(page, "milk")
    add_item(page, "bread")
    page.get_by_role("checkbox", name="bread").check()

    page.get_by_role("button", name="Create an item group").click()
    groups = page.get_by_role("dialog", name="Item groups")
    groups.get_by_role("button", name="New group").click()
    editor = page.get_by_role("dialog", name="New item group")
    editor.get_by_label("Group name").fill("Breakfast")
    editor.get_by_label("Item names, one per line").fill("")
    editor.get_by_role("button", name="Save", exact=True).click()
    expect(
        page.get_by_role("button", name="Breakfast, empty group", exact=True)
    ).to_be_visible()
    assert server.query("SELECT name, items_json FROM item_groups") == [
        ("Breakfast", "[]")
    ]

    page.get_by_role("button", name="Breakfast, empty group", exact=True).click()
    expect(page.get_by_text("No items to add", exact=True)).to_be_visible()
    expect(item_names(page)).to_have_text(["milk", "bread"])

    page.get_by_role("button", name="Manage groups").click()
    groups = page.get_by_role("dialog", name="Item groups")
    expect(groups.get_by_text("Empty group", exact=True)).to_be_visible()
    groups.get_by_role("button", name="Edit").click()
    editor = page.get_by_role("dialog", name="Edit 'Breakfast'")
    editor.get_by_label("Item names, one per line").fill("Milk\nbread\neggs")
    editor.get_by_role("button", name="Save", exact=True).click()
    expect(page.get_by_role("button", name="Breakfast", exact=True)).to_be_visible()
    assert server.query("SELECT name, items_json FROM item_groups") == [
        ("Breakfast", '["Milk", "bread", "eggs"]')
    ]

    page.get_by_role("button", name="Breakfast", exact=True).click()
    expect(page.get_by_text("Added 1; skipped 2 already on the list")).to_be_visible()
    expect(page.get_by_role("checkbox", name="bread")).to_be_checked()
    expect(page.get_by_role("checkbox", name="milk")).not_to_be_checked()
    expect(item_names(page)).to_have_text(["eggs", "milk", "bread"])
    assert server.query(
        "SELECT name, done FROM items ORDER BY name COLLATE NOCASE"
    ) == [
        ("bread", 1),
        ("eggs", 0),
        ("milk", 0),
    ]

    page.get_by_role("button", name="Manage groups").click()
    groups = page.get_by_role("dialog", name="Item groups")
    groups.get_by_role("button", name="Delete", exact=True).click()
    confirmation = page.get_by_role("dialog", name="Delete 'Breakfast'?")
    confirmation.get_by_role("button", name="Delete group").click()
    expect(page.get_by_role("button", name="Breakfast", exact=True)).to_have_count(0)
    assert server.query("SELECT name FROM items ORDER BY name COLLATE NOCASE") == [
        ("bread",),
        ("eggs",),
        ("milk",),
    ]


def test_stale_group_edit_keeps_the_draft_until_explicit_overwrite(
    svelte_server, open_session
):
    server = svelte_server
    first = open_session("first", **PHONE)
    second = open_session("second", **PHONE)
    sign_in(first, server)
    sign_in(second, server)
    list_url = create_list(first, "Groceries")
    first.get_by_role("button", name="Create an item group").click()
    first.get_by_role("dialog", name="Item groups").get_by_role(
        "button", name="New group"
    ).click()
    editor = first.get_by_role("dialog", name="New item group")
    editor.get_by_label("Group name").fill("Original")
    editor.get_by_label("Item names, one per line").fill("milk")
    editor.get_by_role("button", name="Save", exact=True).click()

    second.goto(list_url)
    expect(second.get_by_role("button", name="Original", exact=True)).to_be_visible()
    for page in (first, second):
        page.get_by_role("button", name="Manage groups").click()
        page.get_by_role("dialog", name="Item groups").get_by_role(
            "button", name="Edit"
        ).click()
    first_editor = first.get_by_role("dialog", name="Edit 'Original'")
    second_editor = second.get_by_role("dialog", name="Edit 'Original'")
    first_editor.get_by_label("Group name").fill("My draft")
    first_editor.get_by_label("Item names, one per line").fill("draft item")
    second_editor.get_by_label("Group name").fill("Saved elsewhere")
    second_editor.get_by_label("Item names, one per line").fill("latest item")
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
    expect(first_editor.get_by_label("Item names, one per line")).to_have_value(
        "draft item"
    )
    overwrite = first_editor.get_by_label("Save my draft over the latest version")
    expect(overwrite).not_to_be_checked()
    save_mine = first_editor.get_by_role("button", name="Save my draft")
    expect(save_mine).to_be_disabled()
    overwrite.check()
    save_mine.click()

    expect(first.get_by_role("button", name="My draft", exact=True)).to_be_visible()
    assert server.query("SELECT name, items_json FROM item_groups") == [
        ("My draft", '["draft item"]')
    ]


def test_public_share_does_not_expose_room_item_groups(svelte_server, open_session):
    server = svelte_server
    member = open_session("member", **PHONE)
    visitor = open_session("visitor", **PHONE)
    sign_in(member, server)
    create_list(member, "Groceries")
    member.get_by_role("button", name="Create an item group").click()
    groups = member.get_by_role("dialog", name="Item groups")
    groups.get_by_role("button", name="New group").click()
    editor = member.get_by_role("dialog", name="New item group")
    editor.get_by_label("Group name").fill("Private group")
    editor.get_by_label("Item names, one per line").fill("milk")
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
    expect(visitor.get_by_role("button", name="Create an item group")).to_have_count(0)
    expect(visitor.get_by_role("button", name="Manage groups")).to_have_count(0)
    assert server.query("SELECT name FROM item_groups") == [("Private group",)]
    assert responses and all(response.get("groups") == [] for response in responses)
