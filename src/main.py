import os

from nicegui import ui, context

from database import default_list_id
from models import (
    add_item,
    create_list,
    delete_item,
    find_duplicate_name,
    find_item_by_name,
    get_list_data,
    get_lists,
    normalize_item_name,
    rename_item,
    restore_item,
    update_item_done,
)

ACTIVE_LIST_STORAGE_KEY = "active_list_id"


def get_active_list_id_for_client(client) -> int:
    # Resolve one browser connection's selected list from connection-local storage.
    if client is None:
        return default_list_id
    raw_list_id = client.storage.get(ACTIVE_LIST_STORAGE_KEY)
    if raw_list_id is not None:
        try:
            return int(raw_list_id)
        except (TypeError, ValueError):
            return default_list_id
    return default_list_id


def get_active_list_id() -> int:
    # Read this client/tab's currently selected list id.
    client = context.client
    return get_active_list_id_for_client(client)


def set_active_list_id(list_id: int) -> None:
    # Persist this client/tab's selected list id.
    client = context.client
    if client is None:
        return
    client.storage[ACTIVE_LIST_STORAGE_KEY] = int(list_id)


def broadcast_updates():
    # Push a fresh list view to every connected browser client.
    # item_list reads the active list from each target client at render time.
    item_list.refresh()


@ui.refreshable
def item_list(switch):
    # Render the list rows and wire per-row actions (toggle done, delete).
    active_list_id = get_active_list_id()
    list_items, _ = get_list_data(active_list_id)
    for item in list_items:
        if switch.value and item["done"]:
            continue
        row = ui.row().classes("w-full items-center no-wrap")
        with row:
            # 1. Use the 'done' value from our data
            checkbox = ui.checkbox(value=item["done"])

            # 2. Add the styling immediately if it's already done
            label_style = "line-through text-gray-400" if item["done"] else ""
            ui.label(item["name"]).classes(label_style)

            # 3. Update data AND redraw when clicked
            def toggle(e, it=item):
                # Mark one item done/undone in DB, then broadcast the updated list.
                update_item_done(item_id=it["id"], list_id=active_list_id, done=e.value)
                broadcast_updates()

            checkbox.on_value_change(toggle)

            def start_edit(it=item):
                # Open a rename dialog for one item, then persist and broadcast on save.
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                    new_name_input = ui.input(
                        label="Rename item", value=it["name"]
                    ).classes("w-full")

                    with ui.row().classes("w-full justify-end"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        def save_name():
                            new_name = normalize_item_name(new_name_input.value)
                            if not new_name:
                                ui.notify(
                                    "Name cannot be empty",
                                    color="warning",
                                    position="top",
                                )
                                return

                            duplicate = find_duplicate_name(
                                list_id=active_list_id,
                                item_id=it["id"],
                                new_name=new_name,
                            )
                            if duplicate:
                                ui.notify(
                                    f"'{new_name}' already exists",
                                    color="warning",
                                    position="top",
                                )
                                return

                            rename_item(
                                item_id=it["id"],
                                list_id=active_list_id,
                                new_name=new_name,
                            )
                            dialog.close()
                            ui.notify(
                                f"Renamed to {new_name}",
                                color="positive",
                                position="top",
                            )
                            broadcast_updates()

                        ui.button("Save", on_click=save_name).props("color=primary")

                dialog.open()

            # 4. Remove from data AND redraw when deleted
            def delete(it=item):
                # Delete one item from DB, then broadcast the updated list.
                delete_item(item_id=it["id"], list_id=active_list_id)
                ui.notify(f"Deleted {it['name']}", color="negative", position="top")
                broadcast_updates()

            with ui.row().classes("ml-auto items-center gap-0 -mr-1"):
                ui.button(icon="edit", on_click=start_edit).props(
                    "flat round dense size=0.8rem padding=4px"
                )
                ui.button(icon="delete", on_click=delete).props(
                    "flat round dense size=0.8rem padding=4px"
                )


def add_to_list(target_input, list_id, val=None):
    # Add a new item (or restore an old one), then clear this user's input and refresh all clients.
    raw_name = val if val is not None else target_input.value
    item_name = normalize_item_name(raw_name)
    if not item_name:
        return

    # Check the database for this name
    existing = find_item_by_name(list_id=list_id, item_name=item_name)

    if existing:
        item_id, is_done = existing
        if is_done:
            # It was checked off -> Restore it
            restore_item(item_id=item_id, list_id=list_id)
            ui.notify(f"Restored {item_name}!", color="info", position="top")
        else:
            # It is already on the list -> Warn user
            ui.notify(
                f"'{item_name}' is already on the list",
                color="warning",
                position="top",
            )
    else:
        # It's brand new -> Add it
        add_item(item_name=item_name, list_id=list_id)
        ui.notify(f"Added {item_name}", color="positive", position="top")

    # Reset UI and refresh data
    target_input.value = None
    target_input.update()
    broadcast_updates()


@ui.page("/")
def index():
    # Build the main page: input controls plus the shared list.
    set_active_list_id(get_active_list_id())

    with ui.card().classes("w-full max-w-sm mx-auto"):
        ui.label("Vår handleliste").classes("text-2xl font-bold")

        with ui.row().classes("w-full items-center no-wrap gap-2"):
            list_selector = ui.select(
                options={list_id: name for list_id, name in get_lists()},
                value=get_active_list_id(),
                label="Choose list",
            ).classes("w-full")
            list_selector.props("behavior=menu")

            def open_new_list_dialog():
                # Create a new list from dialog input and switch to it immediately.
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                    list_name_input = ui.input(label="New list name").classes("w-full")
                    with ui.row().classes("w-full justify-end"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        def save_list():
                            try:
                                new_list_id = create_list(list_name_input.value)
                            except ValueError:
                                ui.notify(
                                    "List name cannot be empty",
                                    color="warning",
                                    position="top",
                                )
                                return

                            set_active_list_id(new_list_id)
                            dialog.close()
                            ui.notify("List ready", color="positive", position="top")
                            refresh_selected_list()
                            broadcast_updates()

                        ui.button("Save", on_click=save_list).props("color=primary")
                dialog.open()

            ui.button(icon="add", on_click=open_new_list_dialog).props("flat round")

        hide_switch = ui.switch("Hide Completed")
        # Input field for new items
        search_input = ui.select(
            options=[],
            with_input=True,
            new_value_mode="add",
            label="Add or Search items",
        ).classes("w-full")

        search_input.props("behavior=menu")
        search_input.props("fill-input=false")

        def on_filter(e):
            # Limit dropdown suggestions to at most 3 matches and only after typing starts.
            typed = normalize_item_name((e.args[0] if e.args else "") or "")
            _, active_history_names = get_list_data(get_active_list_id())

            if len(typed) < 1:
                # show nothing until at least 1 character typed
                search_input.options = []
            else:
                # max 3 matches
                matches = [name for name in active_history_names if typed in name.lower()]
                search_input.options = matches[:3]

            search_input.update()

        search_input.on("filter", on_filter)

        def refresh_selected_list():
            # Refresh list-specific data and keep selector options in sync.
            active_list_id = get_active_list_id()
            list_selector.options = {list_id: name for list_id, name in get_lists()}
            list_selector.value = active_list_id
            list_selector.update()
            item_list.refresh()

        def on_list_change(e):
            # Switch active list and redraw this page.
            if e.value is None:
                return
            set_active_list_id(int(e.value))
            refresh_selected_list()
            broadcast_updates()

        list_selector.on_value_change(on_list_change)
        hide_switch.on_value_change(
            lambda e: item_list.refresh()
        )

        search_input.on_value_change(
            lambda e: add_to_list(
                target_input=search_input,
                list_id=get_active_list_id(),
                val=e.value,
            )
        )

        # Button to add item
        ui.button(
            "Add",
            on_click=lambda: add_to_list(search_input, list_id=get_active_list_id()),
        )

        item_list(switch=hide_switch)
        refresh_selected_list()


# Initiate the data from file
get_list_data(default_list_id)


port = int(os.environ.get("PORT", 8080))

# ui.run() starts the web server
ui.run(host="0.0.0.0", port=port, reload=True)
