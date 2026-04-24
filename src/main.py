import os
import uuid
from typing import Literal, TypedDict

from dotenv import load_dotenv
from nicegui import app, ui

# Load environment variables from .env file for local development
load_dotenv()

GLOBAL_APP_PASSWORD = os.environ.get("APP_PASSWORD")

# --- PWA and Assets ---
app.add_static_files("/static", os.path.join(os.path.dirname(__file__), "static"))
ui.add_head_html('<link rel="manifest" href="/static/manifest.json">', shared=True)
ui.add_head_html('<meta name="apple-mobile-web-app-capable" content="yes">', shared=True)
ui.add_head_html('<meta name="apple-mobile-web-app-status-bar-style" content="black">', shared=True)
ui.add_head_html('<link rel="apple-touch-icon" href="/static/icon.svg">', shared=True)
ui.add_head_html('<meta name="theme-color" content="#1976d2">', shared=True)

from database_crud import (
    add_item_with_state,
    create_list,
    find_item_by_name,
    get_item_count,
    get_list_data,
    get_list_details,
    get_lists,
    normalize_item_name,
    update_item_active_tags,
    update_list_tags_settings,
)
from item_service import (
    STATUS_ADDED,
    STATUS_DUPLICATE_ACTIVE,
    STATUS_DUPLICATE_NAME,
    STATUS_INVALID_NAME,
    STATUS_RESTORED,
    add_or_restore_item,
    delete_item_from_list,
    delete_list_and_items,
    rename_item_with_checks,
    rename_list_with_checks,
    toggle_item_done,
)

NOTIFY_POSITION = "top"
TAG_COLORS = ["blue", "green", "red", "orange", "purple", "teal", "pink"]


class ItemUndoPayload(TypedDict):
    id: int
    name: str
    done: bool
    active_tags: list[str]


class TagUndoPayload(TypedDict):
    tag: str


class PendingUndoItem(TypedDict):
    kind: Literal["item"]
    message: str
    payload: ItemUndoPayload
    token: str


class PendingUndoTag(TypedDict):
    kind: Literal["tag"]
    message: str
    payload: TagUndoPayload
    token: str


PendingUndo = PendingUndoItem | PendingUndoTag


class PendingUndoInputItem(TypedDict):
    kind: Literal["item"]
    message: str
    payload: ItemUndoPayload


class PendingUndoInputTag(TypedDict):
    kind: Literal["tag"]
    message: str
    payload: TagUndoPayload


PendingUndoInput = PendingUndoInputItem | PendingUndoInputTag


class ViewState(TypedDict):
    filter_tag: str | None
    edit_mode: bool
    pending_undo: PendingUndo | None
    focus_tag_input: bool


def broadcast_updates() -> None:
    list_of_lists.refresh()
    item_list.refresh()


@ui.refreshable
def list_of_lists() -> None:
    lists = get_lists()

    if not lists:
        ui.label("No lists yet. Create your first one!").classes("text-gray-500 italic")
        return

    for list_id, name, slug in lists:
        with ui.card().classes("w-full mb-1 p-1"):
            with ui.row().classes("w-full items-center no-wrap"):
                ui.button(
                    name, on_click=lambda lid=list_id: ui.navigate.to(f"/list/{lid}")
                ).props("flat").classes("flex-grow text-left text-lg")

                def open_rename_dialog(lid=list_id, lname=name):
                    with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                        ui.label(f"Edit '{lname}'").classes("text-lg font-bold")
                        new_name_input = ui.input(
                            value=lname, label="List Name"
                        ).classes("w-full")
                        with ui.row().classes("w-full justify-end mt-4"):
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
                                    f"Updated {actual_name}",
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


@ui.refreshable
def item_list(list_id: int, filter_func=None, edit_mode_func=None, on_delete=None):
    list_items, _ = get_list_data(list_id)
    details = get_list_details(list_id)
    list_tags = details["list_tags"] if details else []
    quick_tags_active = len(list_tags) > 0

    current_filter = filter_func() if filter_func else None
    is_edit_mode = edit_mode_func() if edit_mode_func else False

    for item in list_items:
        if current_filter and current_filter not in item["active_tags"]:
            continue

        row = ui.row().classes(
            "w-full items-center no-wrap border-b border-gray-100 py-1"
        )
        with row:
            with ui.row().classes("flex-grow min-w-0 items-center no-wrap gap-1"):
                checkbox = ui.checkbox(value=item["done"]).props("dense")
                label_style = "line-through text-gray-400" if item["done"] else ""
                ui.label(item["name"]).classes(f"min-w-0 truncate {label_style}")

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
                if on_delete:
                    on_delete(it)
                    return
                delete_item_from_list(list_id, it["id"])
                broadcast_updates()

            with ui.row().classes("shrink-0 items-center no-wrap gap-0"):
                if quick_tags_active:
                    with ui.row().classes("items-center no-wrap gap-1 mx-1"):
                        for idx, tag in enumerate(list_tags):
                            color = TAG_COLORS[idx % len(TAG_COLORS)]
                            first_letter = tag[0].upper() if tag else "?"
                            is_active = tag in item["active_tags"]

                            def toggle_tag(it=item, t=tag):
                                active = it["active_tags"].copy()
                                if t in active:
                                    active.remove(t)
                                else:
                                    active.append(t)
                                update_item_active_tags(it["id"], list_id, active)
                                broadcast_updates()

                            btn = ui.button(first_letter, on_click=toggle_tag)
                            btn_props = f"round size=12px dense color={color}"
                            if not is_active:
                                btn_props += " outline"
                            btn.props(btn_props)
                if is_edit_mode:
                    ui.button(icon="edit", on_click=start_edit).props(
                        "flat round dense size=sm"
                    ).style("margin: -2px")
                    ui.button(icon="delete", on_click=delete).props(
                        "flat round dense size=sm color=negative"
                    ).style("margin: -2px")


@ui.page("/login")
def login() -> None:
    def try_login() -> None:
        if password.value == GLOBAL_APP_PASSWORD:
            app.storage.user.update({"authenticated": True})
            ui.navigate.to("/")
        else:
            ui.notify("Wrong password", color="negative", position=NOTIFY_POSITION)

    with ui.card().classes("absolute-center"):
        ui.label("Enter password").classes("text-xl font-bold")
        password = ui.input("Password", password=True, password_toggle_button=True).classes("w-full").on("keydown.enter", try_login)
        ui.button("Log in", on_click=try_login).classes("w-full mt-4")


@app.middleware("http")
async def auth_middleware(request, call_next):
    # Only protect the root (dashboard) route for now.
    # The /list/{slug} routes will be unprotected for sharing.
    if request.url.path == "/":
        is_authenticated = app.storage.user.get("authenticated", False)
        # If no password is set in the environment, we effectively disable security
        # to prevent locking the developer out if they forgot to set the .env variable.
        if GLOBAL_APP_PASSWORD and not is_authenticated:
            from fastapi.responses import RedirectResponse
            return RedirectResponse("/login")
    return await call_next(request)


@ui.page("/")
def index() -> None:
    with ui.card().classes("w-full max-w-sm mx-auto"):
        with ui.row().classes(
            "w-full items-center justify-between tracking-tighter mb-2"
        ):
            with ui.row().classes("items-center gap-0 text-3xl"):
                ui.label("List").classes("font-bold text-slate-800")
                ui.label("R").classes("font-black text-primary")

            if GLOBAL_APP_PASSWORD:
                def logout() -> None:
                    app.storage.user.update({"authenticated": False})
                    ui.navigate.to("/login")
                ui.button("Log out", on_click=logout).props("flat size=sm")

        def open_new_list_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label("New List").classes("text-lg font-bold")
                list_name_input = ui.input(label="List name").classes("w-full")
                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def save() -> None:
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


def _build_pending_undo(action: PendingUndoInput, token: str) -> PendingUndo:
    if action["kind"] == "item":
        return {
            "kind": "item",
            "message": action["message"],
            "payload": action["payload"],
            "token": token,
        }

    tag_pending: PendingUndoTag = {
        "kind": "tag",
        "message": action["message"],
        "payload": action["payload"],
        "token": token,
    }
    return tag_pending


def _restore_pending_undo(list_id: int, current: PendingUndo) -> None:
    if current["kind"] == "item":
        payload = current["payload"]
        duplicate = find_item_by_name(list_id, payload["name"])
        if duplicate:
            ui.notify(
                "Cannot undo: item name already exists",
                color="warning",
                position=NOTIFY_POSITION,
            )
            return

        add_item_with_state(
            item_name=payload["name"],
            list_id=list_id,
            done=payload["done"],
            active_tags=payload["active_tags"],
        )
        ui.notify(
            f"Restored {payload['name']}",
            color="positive",
            position=NOTIFY_POSITION,
        )
        return

    payload = current["payload"]
    details_now = get_list_details(list_id)
    if not details_now:
        return

    tags_now = details_now["list_tags"] or []
    if payload["tag"] not in tags_now:
        tags_now.append(payload["tag"])
    tags_now = sorted(tags_now, key=str.lower)
    update_list_tags_settings(list_id, tags_now)
    ui.notify(
        f"Restored tag {payload['tag']}",
        color="positive",
        position=NOTIFY_POSITION,
    )


def _render_header(list_name: str, state: ViewState, undo_bar, tags_ui) -> None:
    with ui.row().classes("w-full items-center mb-2"):
        ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props(
            "flat round"
        )
        ui.label(list_name).classes("text-2xl font-bold flex-grow")
        edit_btn_text = "Done" if state["edit_mode"] else "Edit"
        ui.button(
            edit_btn_text,
            on_click=lambda: (
                state.update({"edit_mode": not state["edit_mode"]}),
                undo_bar.refresh(),
                tags_ui.refresh(),
                item_list.refresh(),
            ),
        ).props("flat")


def _render_add_item_row(list_id: int) -> None:
    draft_text = {"val": ""}

    with ui.row().classes("w-full items-center no-wrap gap-2"):
        search_input = ui.select(
            options=[],
            with_input=True,
            new_value_mode="add",
            label="Add or Search",
        ).classes("flex-grow")

        def submit() -> None:
            selected = normalize_item_name(search_input.value)
            to_add = selected or draft_text["val"]
            if not to_add:
                return

            status, name = add_or_restore_item(list_id, to_add)
            if status == STATUS_RESTORED:
                ui.notify(f"Restored {name}!", color="info", position=NOTIFY_POSITION)
            elif status == STATUS_DUPLICATE_ACTIVE:
                ui.notify(
                    f"'{name}' is already on the list",
                    color="warning",
                    position=NOTIFY_POSITION,
                )
            elif status == STATUS_ADDED:
                ui.notify(f"Added {name}", color="positive", position=NOTIFY_POSITION)

            search_input.value = None
            draft_text["val"] = ""
            search_input.options = []
            search_input.update()
            broadcast_updates()

        ui.button("Add", on_click=submit)

    search_input.props("behavior=menu fill-input=false")

    def on_filter(e) -> None:
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


def _create_undo_bar(
    list_id: int,
    state: ViewState,
    clear_pending_undo,
    tags_ui,
):
    @ui.refreshable
    def undo_bar():
        pending = state["pending_undo"]
        if not state["edit_mode"] or not pending:
            return

        with ui.row().classes(
            "w-full items-center justify-between mt-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded"
        ):
            ui.label(pending["message"]).classes("text-sm")

            def undo() -> None:
                current = state["pending_undo"]
                if not current or current["token"] != pending["token"]:
                    return

                _restore_pending_undo(list_id, current)
                clear_pending_undo()
                tags_ui.refresh()
                item_list.refresh()
                broadcast_updates()

            ui.button("Undo", on_click=undo).props("flat color=primary")

    return undo_bar


def _create_tags_ui(
    list_id: int,
    state: ViewState,
    set_pending_undo,
):
    @ui.refreshable
    def tags_ui():
        curr_details = get_list_details(list_id)
        list_tags = sorted(curr_details["list_tags"], key=str.lower) if curr_details else []
        quick_tags_active = len(list_tags) > 0

        if state["edit_mode"]:
            with ui.row().classes("w-full items-center mt-2 gap-2"):
                new_tag_input = ui.input("Add Tag").classes("flex-grow")

                def add_tag() -> None:
                    tag = new_tag_input.value.strip()
                    if tag and tag not in list_tags:
                        updated_tags = sorted(list_tags + [tag], key=str.lower)
                        update_list_tags_settings(list_id, updated_tags)
                        state["focus_tag_input"] = True
                        new_tag_input.value = ""
                        tags_ui.refresh()
                        item_list.refresh()
                        broadcast_updates()

                ui.button(icon="add", on_click=add_tag).props("flat round dense")
                new_tag_input.on("keyup.enter", add_tag)
                if state["focus_tag_input"]:
                    state["focus_tag_input"] = False
                    ui.timer(
                        0.0,
                        lambda inp=new_tag_input: inp.run_method("focus"),
                        once=True,
                    )

        if quick_tags_active:
            with ui.row().classes("w-full gap-2 mt-2 flex-wrap"):
                for idx, tag in enumerate(list_tags):
                    color = TAG_COLORS[idx % len(TAG_COLORS)]
                    is_active = state["filter_tag"] == tag

                    def toggle_filter(t=tag) -> None:
                        if state["filter_tag"] == t:
                            state["filter_tag"] = None
                        else:
                            state["filter_tag"] = t
                        tags_ui.refresh()
                        item_list.refresh()

                    def delete_tag(t=tag) -> None:
                        if t in list_tags:
                            updated_tags = [x for x in list_tags if x != t]
                            update_list_tags_settings(list_id, updated_tags)
                            ui.notify(
                                f"Deleted tag {t}",
                                color="negative",
                                position=NOTIFY_POSITION,
                            )
                            if state["filter_tag"] == t:
                                state["filter_tag"] = None
                            tag_undo: PendingUndoInputTag = {
                                "kind": "tag",
                                "message": f"Deleted tag {t}",
                                "payload": {"tag": t},
                            }
                            set_pending_undo(tag_undo)
                            tags_ui.refresh()
                            item_list.refresh()
                            broadcast_updates()

                    with ui.row().classes("items-center no-wrap gap-0"):
                        btn = ui.button(tag, on_click=toggle_filter)
                        btn_props = f"rounded size=12px color={color}"
                        if not is_active:
                            btn_props += " outline"
                        btn.props(btn_props).classes("px-2")

                        if state["edit_mode"]:
                            del_btn = ui.button(icon="close", on_click=delete_tag)
                            del_btn_props = f"rounded size=sm color={color} flat dense"
                            del_btn.props(del_btn_props)

    return tags_ui


def _delete_item_with_undo(list_id: int, it: dict, set_pending_undo) -> None:
    payload: ItemUndoPayload = {
        "id": it["id"],
        "name": it["name"],
        "done": it["done"],
        "active_tags": it["active_tags"].copy(),
    }
    delete_item_from_list(list_id, it["id"])
    ui.notify(
        f"Deleted {it['name']}",
        color="negative",
        position=NOTIFY_POSITION,
    )
    item_undo: PendingUndoInputItem = {
        "kind": "item",
        "message": f"Deleted {it['name']}",
        "payload": payload,
    }
    set_pending_undo(item_undo)
    item_list.refresh()
    broadcast_updates()


@ui.page("/list/{list_id}")
def list_page(list_id: int):
    list_id = int(list_id)
    details = get_list_details(list_id)
    if not details:
        ui.label("List not found").classes("text-xl p-4")
        return
    list_name = details["name"]

    state: ViewState = {
        "filter_tag": None,
        "edit_mode": False,
        "pending_undo": None,
        "focus_tag_input": False,
    }

    def set_pending_undo(action: PendingUndoInput) -> None:
        token = str(uuid.uuid4())
        state["pending_undo"] = _build_pending_undo(action, token)
        undo_bar.refresh()

        def expire() -> None:
            current_pending = state["pending_undo"]
            if current_pending and current_pending["token"] == token:
                state["pending_undo"] = None
                undo_bar.refresh()

        ui.timer(5.0, expire, once=True)

    def clear_pending_undo() -> None:
        state["pending_undo"] = None
        undo_bar.refresh()

    with ui.card().classes("w-full max-w-sm mx-auto"):
        tags_ui = _create_tags_ui(
            list_id=list_id,
            state=state,
            set_pending_undo=set_pending_undo,
        )
        undo_bar = _create_undo_bar(
            list_id=list_id,
            state=state,
            clear_pending_undo=clear_pending_undo,
            tags_ui=tags_ui,
        )

        _render_header(list_name=list_name, state=state, undo_bar=undo_bar, tags_ui=tags_ui)
        _render_add_item_row(list_id=list_id)
        undo_bar()
        tags_ui()

        item_list(
            list_id,
            lambda: state["filter_tag"],
            lambda: state["edit_mode"],
            lambda it: _delete_item_with_undo(list_id, it, set_pending_undo),
        )


port = int(os.environ.get("PORT", 8080))
ui.run(
    host="0.0.0.0",
    port=port,
    reload=True,
    title="ListR",
    storage_secret="some_secret",
)
