import os

from nicegui import ui, context

from database_crud import (
    create_list,
    get_item_count,
    get_list_data,
    get_lists,
    normalize_item_name,
)
from item_service import (
    STATUS_ADDED,
    STATUS_DELETED,
    STATUS_DUPLICATE_ACTIVE,
    STATUS_DUPLICATE_NAME,
    STATUS_INVALID_NAME,
    STATUS_RENAMED,
    STATUS_RESTORED,
    add_or_restore_item,
    delete_item_from_list,
    delete_list_and_items,
    rename_item_with_checks,
    rename_list_with_checks,
    toggle_item_done,
)

NOTIFY_POSITION = "top"


def broadcast_updates():
    # Push a fresh view to every connected browser client.
    # We refresh both the main list of lists and the item list.
    list_of_lists.refresh()
    item_list.refresh()


@ui.refreshable
def list_of_lists():
    # Render the start page content: a list of all shopping lists.
    lists = get_lists()

    if not lists:
        ui.label("No lists yet. Create your first one!").classes("text-gray-500 italic")
        return

    for list_id, name in lists:
        with ui.card().classes("w-full mb-2"):
            with ui.row().classes("w-full items-center no-wrap"):
                # Main button to enter the list
                ui.button(
                    name, on_click=lambda lid=list_id: ui.navigate.to(f"/list/{lid}")
                ).props("flat").classes("flex-grow text-left text-lg")

                # Edit/Rename button
                def open_rename_dialog(lid=list_id, lname=name):
                    with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                        ui.label(f"Rename '{lname}'").classes("text-lg font-bold")
                        new_name_input = ui.input(value=lname).classes("w-full")
                        with ui.row().classes("w-full justify-end"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")

                            def save():
                                status, actual_name = rename_list_with_checks(
                                    lid, new_name_input.value
                                )
                                if status == STATUS_INVALID_NAME:
                                    ui.notify("Name cannot be empty", color="warning")
                                    return
                                if status == STATUS_DUPLICATE_NAME:
                                    ui.notify(
                                        f"'{actual_name}' already exists",
                                        color="warning",
                                        position=NOTIFY_POSITION,
                                    )
                                    return
                                dialog.close()
                                ui.notify(
                                    f"Renamed to {actual_name}",
                                    color="positive",
                                    position=NOTIFY_POSITION,
                                )
                                broadcast_updates()

                            ui.button("Save", on_click=save)
                        new_name_input.on("keyup.enter", save)
                    dialog.open()

                ui.button(icon="edit", on_click=open_rename_dialog).props(
                    "flat round dense size=sm"
                )

                # Delete button
                def open_delete_dialog(lid=list_id, lname=name):
                    count = get_item_count(lid)
                    with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                        ui.label(f"Delete '{lname}' and its {count} items?").classes(
                            "text-lg"
                        )
                        with ui.row().classes("w-full justify-end"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")

                            def confirm():
                                delete_list_and_items(lid)
                                dialog.close()
                                ui.notify(
                                    f"Deleted '{lname}'",
                                    color="negative",
                                    position=NOTIFY_POSITION,
                                )
                                broadcast_updates()

                            ui.button("Delete", on_click=confirm).props(
                                "color=negative"
                            )
                    dialog.open()

                ui.button(icon="delete", on_click=open_delete_dialog).props(
                    "flat round dense size=sm color=negative"
                )


@ui.page("/")
def index():
    # Start Page: Management of all lists.
    with ui.card().classes("w-full max-w-sm mx-auto"):
        # ui.label("ListR").classes(
        #     "text-3xl font-black tracking-tighter text-primary mb-4"
        # )
        with ui.row().classes(
            "w-full items-center justify-center tracking-tighter gap-0 mb-2 text-3xl"
        ):
            ui.label("List").classes("font-bold text-slate-800")
            ui.label("R").classes("font-black text-primary")

        # Dialog for creating new lists
        def open_new_list_dialog():
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label("New List").classes("text-lg font-bold")
                list_name_input = ui.input(label="List name").classes("w-full")
                with ui.row().classes("w-full justify-end"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def save():
                        try:
                            new_id = create_list(list_name_input.value)
                            dialog.close()
                            ui.notify(
                                "List created",
                                color="positive",
                                position=NOTIFY_POSITION,
                            )
                            ui.navigate.to(f"/list/{new_id}")
                            broadcast_updates()
                        except ValueError:
                            ui.notify(
                                "Name cannot be empty",
                                color="warning",
                                position=NOTIFY_POSITION,
                            )

                    ui.button("Save", on_click=save)

                list_name_input.on("keyup.enter", save)
            dialog.open()

        ui.button("Add New List", icon="add", on_click=open_new_list_dialog).classes(
            "w-full mb-4"
        ).props("outline")

        list_of_lists()


@ui.refreshable
def item_list(list_id: int):
    # Render items for a specific list.
    list_items, _ = get_list_data(list_id)
    for item in list_items:
        row = ui.row().classes(
            "w-full items-center no-wrap border-b border-gray-100 py-1"
        )
        with row:
            checkbox = ui.checkbox(value=item["done"])
            label_style = "line-through text-gray-400" if item["done"] else ""
            ui.label(item["name"]).classes(f"flex-grow {label_style}")

            def toggle(e, it=item):
                toggle_item_done(list_id=list_id, item_id=it["id"], done=e.value)
                broadcast_updates()

            checkbox.on_value_change(toggle)

            def start_edit(it=item):
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                    ui.label("Edit Item").classes("text-lg font-bold")
                    new_name_input = ui.input(value=it["name"]).classes("w-full")
                    with ui.row().classes("w-full justify-end"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        def save():
                            status, new_name = rename_item_with_checks(
                                list_id, it["id"], new_name_input.value
                            )
                            if status == STATUS_INVALID_NAME:
                                ui.notify(
                                    "Name cannot be empty",
                                    color="warning",
                                    position=NOTIFY_POSITION,
                                )
                                return
                            if status == STATUS_DUPLICATE_NAME:
                                ui.notify(
                                    f"'{new_name}' already exists",
                                    color="warning",
                                    position=NOTIFY_POSITION,
                                )
                                return
                            dialog.close()
                            broadcast_updates()

                        ui.button("Save", on_click=save)
                    new_name_input.on("keyup.enter", save)
                dialog.open()

            def delete(it=item):
                delete_item_from_list(list_id, it["id"])
                ui.notify(
                    f"Deleted {it['name']}", color="negative", position=NOTIFY_POSITION
                )
                broadcast_updates()

            with ui.row().classes("items-center gap-0"):
                ui.button(icon="edit", on_click=start_edit).props(
                    "flat round dense size=sm"
                )
                ui.button(icon="delete", on_click=delete).props(
                    "flat round dense size=sm color=negative"
                )


@ui.page("/list/{list_id}")
def list_page(list_id: int):
    # Detail View: Focus on items within a specific list.
    list_id = int(list_id)
    lists = dict(get_lists())
    list_name = lists.get(list_id, "Unknown List")

    with ui.card().classes("w-full max-w-sm mx-auto"):
        # Header with back button
        with ui.row().classes("w-full items-center mb-2"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props(
                "flat round"
            )
            ui.label(list_name).classes("text-2xl font-bold flex-grow")

        # Add item input
        draft_text = {"val": ""}  # Use dict to keep it mutable in inner functions

        with ui.row().classes("w-full items-center no-wrap gap-2"):
            search_input = ui.select(
                options=[],
                with_input=True,
                new_value_mode="add",
                label="Add or Search",
            ).classes("flex-grow")

            def submit():
                selected = normalize_item_name(search_input.value)
                to_add = selected or draft_text["val"]
                if not to_add:
                    return

                status, name = add_or_restore_item(list_id, to_add)
                if status == STATUS_RESTORED:
                    ui.notify(
                        f"Restored {name}!", color="info", position=NOTIFY_POSITION
                    )
                elif status == STATUS_DUPLICATE_ACTIVE:
                    ui.notify(
                        f"'{name}' is already on the list",
                        color="warning",
                        position=NOTIFY_POSITION,
                    )
                elif status == STATUS_ADDED:
                    ui.notify(
                        f"Added {name}", color="positive", position=NOTIFY_POSITION
                    )

                search_input.value = None
                draft_text["val"] = ""
                search_input.options = []
                search_input.update()
                broadcast_updates()

            ui.button("Add", on_click=submit)

        search_input.props("behavior=menu fill-input=false")

        def on_filter(e):
            typed = normalize_item_name(e.args[0] if e.args else "")
            draft_text["val"] = typed
            if len(typed) < 1:
                search_input.options = []
            else:
                _, history = get_list_data(list_id)
                matches = [n for n in history if typed in n.lower()]
                search_input.options = matches[:3]
            search_input.update()

        search_input.on("filter", on_filter)
        search_input.on("keyup.enter", submit)
        search_input.on_value_change(
            lambda e: draft_text.update({"val": normalize_item_name(e.value or "")})
        )

        # The actual list of items
        item_list(list_id)


port = int(os.environ.get("PORT", 8080))
ui.run(
    host="0.0.0.0",
    port=port,
    reload=True,
    title="ListR",
    storage_secret="some_secret",
)
