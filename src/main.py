import json
import os
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import suppress
from typing import Literal, TypedDict
from urllib.parse import quote, urlsplit

from nicegui import app, core, ui

from config import app_reload_enabled, require_app_password
from ui.install_help import install_help_menu_item
from ui.room_invitations import creation_form, invitation_controls
from ui.sharing import share_button

GLOBAL_APP_PASSWORD = require_app_password()

from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse


# --- PWA and Assets ---
@app.get("/sw.js")
def serve_service_worker():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "sw.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/manifest.json")
@app.get("/static/manifest.json")
def serve_manifest():
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "manifest.json"),
        media_type="application/json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/room-manifest/{slug}.json")
def serve_room_manifest(slug: str):
    # This is routing metadata, never proof of authorization. Do not include
    # room names, passwords, tokens, or incoming query parameters.
    if not get_room_details_by_slug(slug):
        raise HTTPException(status_code=404, detail="Room not found")
    with open(
        os.path.join(os.path.dirname(__file__), "static", "manifest.json"),
        encoding="utf-8",
    ) as manifest_file:
        manifest = json.load(manifest_file)
    manifest["start_url"] = f"/room/{quote(slug, safe='')}"
    return JSONResponse(
        manifest,
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


def _add_install_manifest(room_slug: str | None = None) -> None:
    href = (
        f"/room-manifest/{quote(room_slug, safe='')}.json"
        if room_slug is not None
        else "/manifest.json"
    )
    ui.add_head_html(f'<link rel="manifest" href="{href}">')


app.add_static_files("/static", os.path.join(os.path.dirname(__file__), "static"))
ui.add_head_html(
    '<meta name="apple-mobile-web-app-capable" content="yes">', shared=True
)
ui.add_head_html(
    '<meta name="apple-mobile-web-app-status-bar-style" content="black">', shared=True
)
ui.add_head_html(
    '<link rel="apple-touch-icon" sizes="180x180" href="/static/icons/apple-touch-icon.png">',
    shared=True,
)
ui.add_head_html(
    '<link rel="icon" type="image/png" sizes="32x32" href="/static/icons/favicon-32.png">',
    shared=True,
)
ui.add_head_html(
    '<link rel="icon" type="image/png" sizes="16x16" href="/static/icons/favicon-16.png">',
    shared=True,
)
ui.add_head_html(
    '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">',
    shared=True,
)
ui.add_head_html('<meta name="theme-color" content="#1976d2">', shared=True)
ui.add_head_html(
    """
    <style>
      /* Keep custom light utility colors legible when Quasar dark mode is active. */
      .body--dark .bg-slate-50, .body--dark .bg-slate-100 {
        background-color: #303030 !important;
      }
      .body--dark .bg-amber-50 { background-color: #403727 !important; }
      .body--dark .border-slate-200, .body--dark .border-amber-200 {
        border-color: #555 !important;
      }
      .body--dark .text-slate-800, .body--dark .text-slate-700,
      .body--dark .text-gray-700, .body--dark .text-gray-600,
      .body--dark .text-gray-500 { color: #ddd !important; }
      /* Prevent auto-zoom on mobile input focus */
      input, select, textarea, .q-field__native, .q-field__input {
        font-size: 16px !important;
      }
    </style>
    """,
    shared=True,
)
ui.add_head_html(
    """
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js')
        .then(reg => {
          reg.update();
        })
        .catch(err => console.error('SW Registration Failed:', err));
    });

    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible' && navigator.serviceWorker.controller) {
        navigator.serviceWorker.ready.then(reg => reg.update());
      }
    });
  }
</script>
""",
    shared=True,
)

from database_crud import (
    ListUnavailable,
    RoomAccessDenied,
    authenticate_room_and_issue_token,
    change_room_password_and_issue_token,
    create_list,
    create_list_with_room_token,
    create_room,
    delete_list_with_room_token,
    delete_room_with_password,
    get_item_count,
    get_list_data,
    get_list_details,
    get_list_details_by_identity,
    get_list_details_by_share_token,
    get_list_details_by_slug,
    get_lists,
    get_room_details_by_slug,
    get_rooms,
    list_identity_matches,
    normalize_item_name,
    rename_list_with_room_token,
    rename_room,
    rename_room_with_room_token,
    restore_deleted_item,
    revoke_room_access_token,
    rotate_list_share_token,
    update_item_active_tags,
    update_list_tags_settings,
    update_room_password,
)
from item_service import (
    STATUS_ADDED,
    STATUS_DUPLICATE_ACTIVE,
    STATUS_DUPLICATE_NAME,
    STATUS_INVALID_NAME,
    STATUS_RESTORED,
    add_or_restore_item,
    change_item_quantity,
    delete_item_from_list,
    delete_list_and_items,
    rename_list_with_checks,
    toggle_item_done,
    update_item_details_with_checks,
)
from room_access import RoomAccess, RoomAccessStatus
from room_cookies import (
    LAST_ROOM_COOKIE,
    register_room_cookie_routes,
    same_origin_socket,
    token_cookie_name,
)

register_room_cookie_routes(app)
# Cookie credentials require same-origin websocket and polling handshakes.
core.sio.eio.cors_allowed_origins = same_origin_socket

NOTIFY_POSITION = "top"
TAG_COLORS = ["blue", "green", "red", "orange", "purple", "teal", "pink"]

# TODO(room-access-token-migration): Legacy password-key cleanup was added on
# 2026-09-18. Remove this cleanup after 2027-09-18, but retain token handling.


def _room_token_storage_key(room_slug: str) -> str:
    return f"listapp_room_token_{room_slug}"


async def _cleanup_legacy_room_password_keys() -> bool:
    """Delete only old password keys; token and last-room keys must survive."""
    try:
        await ui.run_javascript(
            """
            const legacyKeys = Object.keys(localStorage).filter(
                (key) => key.startsWith('listapp_room_')
                    && !key.startsWith('listapp_room_token_')
            );
            for (const key of legacyKeys) {
                localStorage.removeItem(key);
            }
            return true;
            """,
            timeout=3.0,
        )
    except Exception:  # noqa: BLE001 - browser storage can be unavailable.
        return False
    return True


async def _get_browser_storage(key: str) -> tuple[bool, str | None]:
    """Read remembered cookies first, then migrate legacy browser storage."""
    request = ui.context.client.request
    prefix = "listapp_room_token_"
    if request.url.scheme == "https":
        cookie_key = (
            token_cookie_name(key[len(prefix) :])
            if key.startswith(prefix)
            else LAST_ROOM_COOKIE
            if key == "listapp_last_room"
            else None
        )
        if cookie_key and (value := request.cookies.get(cookie_key)):
            return True, value
    try:
        value = await ui.run_javascript(
            f"return localStorage.getItem({json.dumps(key)})", timeout=3.0
        )
    except Exception:  # noqa: BLE001 - browser storage can be unavailable.
        return False, None
    if isinstance(value, str) and key.startswith(prefix):
        await _store_room_cookie(key[len(prefix) :], value)
    return True, value if isinstance(value, str) else None


async def _store_room_cookie(room_slug: str, token: str) -> bool:
    try:
        return bool(
            await ui.run_javascript(
                """
            if (location.protocol !== 'https:') return false;
            const url = '/_room-access/' + encodeURIComponent(%s);
            const token = %s;
            const send = (body) => fetch(url, {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json', 'X-Listapp-Request': '1'},
                body: JSON.stringify(body),
            });
            if (!(await send({token})).ok) return false;
            if (!(await send({token, check: true})).ok) return false;
            try {
                localStorage.removeItem(%s);
                localStorage.setItem('listapp_last_room', %s);
            } catch (_) { /* Confirmed cookies need no localStorage. */ }
            return true;
            """
                % (
                    json.dumps(room_slug),
                    json.dumps(token),
                    json.dumps(_room_token_storage_key(room_slug)),
                    json.dumps(room_slug),
                ),
                timeout=5.0,
            )
        )
    except Exception:  # noqa: BLE001 - preserve legacy access on network failure.
        return False


async def _store_room_access(room_slug: str, token: str) -> bool:
    if await _store_room_cookie(room_slug, token):
        return True
    token_key = _room_token_storage_key(room_slug)
    try:
        await ui.run_javascript(
            """
            localStorage.setItem(%s, %s);
            localStorage.setItem('listapp_last_room', %s);
            return true;
            """
            % (json.dumps(token_key), json.dumps(token), json.dumps(room_slug)),
            timeout=3.0,
        )
    except Exception:  # noqa: BLE001 - browser storage can be unavailable.
        return False
    return True


async def _remove_room_token(room_slug: str) -> None:
    with suppress(
        Exception
    ):  # Browser cleanup is best effort for a known invalid token.
        await ui.run_javascript(
            """
            if (location.protocol === 'https:') {
                await fetch('/_room-access/' + encodeURIComponent(%s), {
                    method: 'POST', credentials: 'same-origin',
                    headers: {'Content-Type': 'application/json', 'X-Listapp-Request': '1'},
                    body: JSON.stringify({clear: true}),
                });
            }
            localStorage.removeItem(%s);
            """
            % (json.dumps(room_slug), json.dumps(_room_token_storage_key(room_slug))),
            timeout=3.0,
        )


def _remember_authorized_room(room_slug: str) -> None:
    authorized_rooms = app.storage.user.get("authorized_rooms", [])
    if room_slug not in authorized_rooms:
        authorized_rooms = [*authorized_rooms, room_slug]
    app.storage.user.update(
        {"authorized_rooms": authorized_rooms, "last_room_slug": room_slug}
    )


def _forget_authorized_room(room_slug: str) -> None:
    authorized_rooms = app.storage.user.get("authorized_rooms", [])
    app.storage.user.update(
        {"authorized_rooms": [slug for slug in authorized_rooms if slug != room_slug]}
    )


async def _require_private_room_access(access: RoomAccess) -> bool:
    """Guard every private callback without trusting browser or user-storage caches."""
    status = access.check()
    if status is RoomAccessStatus.VALID:
        return True
    if status is RoomAccessStatus.UNAVAILABLE:
        ui.notify(
            "Could not verify room access. Please retry; saved access was kept.",
            color="warning",
            position=NOTIFY_POSITION,
        )
        return False

    _forget_authorized_room(access.room_slug)
    if access.token:
        await _remove_room_token(access.room_slug)
    ui.notify(
        "Room access has expired. Enter the password again.",
        color="warning",
        position=NOTIFY_POSITION,
    )
    ui.navigate.to(f"/room/{access.room_slug}")
    return False


class ItemUndoPayload(TypedDict):
    name: str
    done: bool
    active_tags: list[str]
    description: str
    quantity: int


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
    show_counters: bool
    only_gt_1: bool


class ListPageState(TypedDict):
    status: Literal["active", "unavailable"]
    list_id: int | None
    list_slug: str
    list_name: str | None
    room_slug: str | None
    room_authorized: bool


ListLookupStatus = Literal["exists", "missing", "retry"]


def _list_lookup_status(slug: str) -> ListLookupStatus:
    """Distinguish a missing list from a temporary database read failure."""
    try:
        details = (
            get_list_details_by_share_token(slug.removeprefix("share:"))
            if slug.startswith("share:")
            else get_list_details_by_slug(slug)
        )
        return "exists" if details else "missing"
    except sqlite3.Error:
        return "retry"


def _unavailable_list_message(room_access_valid: bool) -> str:
    if room_access_valid:
        return "This list was deleted."
    return "This list was deleted or you no longer have access."


def _can_return_to_room(
    room_access_status: RoomAccessStatus, room_exists: bool
) -> bool:
    return room_exists and room_access_status is RoomAccessStatus.VALID


def _transition_list_state(state: ListPageState) -> bool:
    """Mark a list unavailable once and report whether a transition occurred."""
    if state["status"] == "unavailable":
        return False
    state["status"] = "unavailable"
    return True


class LiveClientRefreshable(ui.refreshable):
    """Ignore refresh targets whose NiceGUI client was already deleted."""

    def prune(self) -> None:
        # NiceGUI checks is_deleted, but a container can outlive its weak client
        # reference without being marked deleted. Refreshing it aborts the whole
        # batch, leaving other open list pages unchanged.
        super().prune()
        live_targets = []
        for target in self.targets:
            try:
                target.container.client
            except RuntimeError as error:
                if str(error) != "The client this element belongs to has been deleted.":
                    raise
            else:
                live_targets.append(target)
        self.targets = live_targets


def broadcast_updates(refresh_lists: bool = True, refresh_items: bool = True) -> None:
    # Do not pass kwargs into refresh(): NiceGUI merges kwargs into all refresh targets.
    # Passing one user's room kwargs can therefore overwrite other users' room context.
    if refresh_lists:
        list_of_lists.refresh()
    if refresh_items:
        item_list.refresh()


@LiveClientRefreshable
def list_of_lists(room_id: int, room_slug: str, access: RoomAccess) -> None:
    """Render private room lists only while this page's access remains valid."""
    access_status = access.check()
    if access_status is RoomAccessStatus.UNAVAILABLE:
        with ui.column().classes("w-full items-center gap-2"):
            ui.label("Could not verify room access. Please retry.").classes(
                "text-gray-500 italic"
            )
            ui.button("Retry", on_click=list_of_lists.refresh).props("flat")
        return
    if access_status is RoomAccessStatus.INVALID:
        _forget_authorized_room(room_slug)
        ui.label("Room access has expired. Reopen the room to sign in again.").classes(
            "text-gray-500 italic"
        )
        return

    lists = get_lists(room_id)
    if not lists:
        ui.label("No lists yet. Create your first one!").classes("text-gray-500 italic")
        return

    for list_id, name, slug in lists:
        with (
            ui.card().classes("w-full mb-1 p-1"),
            ui.row().classes("w-full items-center no-wrap"),
        ):
            ui.button(name, on_click=lambda s=slug: ui.navigate.to(f"/list/{s}")).props(
                "flat"
            ).classes("flex-grow text-left text-lg")

            def open_rename_dialog(lid=list_id, lname=name, lslug=slug):
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                    ui.label(f"Edit '{lname}'").classes("text-lg font-bold")
                    new_name_input = ui.input(value=lname, label="List Name").classes(
                        "w-full"
                    )
                    with ui.row().classes("w-full justify-end mt-4"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        async def save() -> None:
                            if not await _require_private_room_access(access):
                                return
                            try:
                                if access.is_admin():
                                    status, actual_name = rename_list_with_checks(
                                        lid,
                                        room_id,
                                        new_name_input.value,
                                        expected_slug=lslug,
                                    )
                                    if status == STATUS_INVALID_NAME:
                                        ui.notify(
                                            "Name cannot be empty", color="warning"
                                        )
                                        return
                                    if status == STATUS_DUPLICATE_NAME:
                                        ui.notify(
                                            f"'{actual_name}' already exists in this room",
                                            color="warning",
                                            position=NOTIFY_POSITION,
                                        )
                                        return
                                else:
                                    actual_name = rename_list_with_room_token(
                                        room_slug,
                                        access.token or "",
                                        lid,
                                        new_name_input.value,
                                        expected_slug=lslug,
                                    )
                            except RoomAccessDenied:
                                await _require_private_room_access(access)
                                return
                            except ListUnavailable:
                                dialog.close()
                                ui.notify(
                                    "The list is no longer available.",
                                    color="warning",
                                    position=NOTIFY_POSITION,
                                )
                                list_of_lists.refresh()
                                return
                            except ValueError as error:
                                ui.notify(
                                    str(error),
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

            async def open_delete_dialog(lid=list_id, lname=name, lslug=slug) -> None:
                if not await _require_private_room_access(access):
                    return
                count = get_item_count(lid)
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                    ui.label(f"Delete '{lname}' and its {count} items?").classes(
                        "text-lg"
                    )
                    with ui.row().classes("w-full justify-end"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        async def confirm() -> None:
                            if not await _require_private_room_access(access):
                                return
                            try:
                                if access.is_admin():
                                    delete_list_and_items(
                                        lid, room_id, expected_slug=lslug
                                    )
                                else:
                                    delete_list_with_room_token(
                                        room_slug,
                                        access.token or "",
                                        lid,
                                        expected_slug=lslug,
                                    )
                            except RoomAccessDenied:
                                await _require_private_room_access(access)
                                return
                            except ListUnavailable:
                                dialog.close()
                                ui.notify(
                                    "The list is no longer available.",
                                    color="warning",
                                    position=NOTIFY_POSITION,
                                )
                                list_of_lists.refresh()
                                return
                            dialog.close()
                            ui.notify(
                                f"Deleted '{lname}'",
                                color="negative",
                                position=NOTIFY_POSITION,
                            )
                            broadcast_updates(refresh_lists=True, refresh_items=False)

                        ui.button("Delete", on_click=confirm).props("color=negative")
                dialog.open()

            ui.button(icon="delete", on_click=open_delete_dialog).props(
                "flat round dense size=sm color=negative"
            )


@LiveClientRefreshable
def item_list(
    list_id: int,
    filter_func=None,
    edit_mode_func=None,
    on_delete=None,
    show_counters_func=None,
    only_gt_1_func=None,
    is_active: Callable[[], bool] | None = None,
    on_unavailable: Callable[[], None] | None = None,
    *,
    list_slug: str,
):
    if is_active and not is_active():
        return

    details = get_list_details(list_id)
    if details is None or not list_identity_matches(details, list_slug):
        if on_unavailable:
            # Defer the parent-container replacement until this refresh completes.
            ui.timer(0.0, on_unavailable, once=True)
        return

    list_items, _ = get_list_data(list_id)
    list_tags = details["list_tags"]
    quick_tags_active = len(list_tags) > 0

    current_filter = filter_func() if filter_func else None
    is_edit_mode = edit_mode_func() if edit_mode_func else False
    show_counters = show_counters_func() if show_counters_func else False
    only_gt_1 = only_gt_1_func() if only_gt_1_func else False

    for item in list_items:
        if current_filter and current_filter not in item["active_tags"]:
            continue

        row = ui.row().classes(
            "w-full items-center justify-between no-wrap border-b border-gray-100 py-1"
        )
        with row:

            def delete(it=item):
                if is_active and not is_active():
                    return
                try:
                    if on_delete:
                        on_delete(it)
                        return
                    delete_item_from_list(list_id, it["id"], expected_slug=list_slug)
                except ListUnavailable:
                    if on_unavailable:
                        on_unavailable()
                    return
                broadcast_updates()

            def open_edit_dialog(it=item):
                if is_active and not is_active():
                    return
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm gap-3"):
                    ui.label("Edit Item").classes("text-lg font-bold")
                    name_input = ui.input(label="Item Name", value=it["name"]).classes(
                        "w-full"
                    )
                    desc_input = (
                        ui.textarea(
                            label="Description / Notes",
                            value=it.get("description", ""),
                        )
                        .classes("w-full")
                        .props("rows=3")
                    )

                    with ui.row().classes(
                        "w-full items-center justify-between mt-1 px-1 py-1 bg-slate-50 rounded border border-slate-200"
                    ):
                        ui.label("Quantity").classes(
                            "text-sm text-gray-700 font-medium"
                        )
                        q_val = {"count": it.get("quantity", 1)}
                        with ui.row().classes("items-center gap-1"):

                            def dec_q():
                                q_val["count"] = max(1, q_val["count"] - 1)
                                q_label.text = str(q_val["count"])

                            def inc_q():
                                q_val["count"] += 1
                                q_label.text = str(q_val["count"])

                            ui.button("-", on_click=dec_q).props(
                                "flat round dense size=sm color=primary"
                            )
                            q_label = ui.label(str(q_val["count"])).classes(
                                "px-2 font-bold text-slate-800 text-base"
                            )
                            ui.button("+", on_click=inc_q).props(
                                "flat round dense size=sm color=primary"
                            )

                    def save():
                        if is_active and not is_active():
                            return
                        try:
                            status, new_name = update_item_details_with_checks(
                                list_id,
                                it["id"],
                                name_input.value,
                                desc_input.value,
                                q_val["count"],
                                expected_slug=list_slug,
                            )
                        except ListUnavailable:
                            if on_unavailable:
                                on_unavailable()
                            return
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

                    with ui.row().classes("w-full justify-between items-center pt-2"):

                        def handle_delete():
                            dialog.close()
                            delete(it)

                        ui.button(icon="delete", on_click=handle_delete).props(
                            "flat round dense color=negative"
                        ).tooltip("Delete Item")
                        with ui.row().classes("gap-2"):
                            ui.button("Cancel", on_click=dialog.close).props("flat")
                            ui.button("Save", on_click=save)

                    name_input.on("keyup.enter", save)
                dialog.open()

            # Left side: Checkbox, Name, Description Icon
            with ui.row().classes("flex-grow min-w-0 items-center no-wrap gap-2"):
                checkbox = ui.checkbox(value=item["done"]).props("dense")
                label_style = "line-through text-gray-400" if item["done"] else ""
                title_label = ui.label(item["name"]).classes(
                    f"min-w-0 truncate cursor-pointer hover:text-primary {label_style}"
                )
                title_label.on("click", lambda _e, it=item: open_edit_dialog(it))

                if item.get("description"):
                    ui.icon("description", size="16px").classes(
                        "text-slate-400 shrink-0 cursor-pointer"
                    ).tooltip(item["description"]).on(
                        "click", lambda _e, it=item: open_edit_dialog(it)
                    )

            def toggle(e, it=item):
                if is_active and not is_active():
                    return
                try:
                    toggle_item_done(
                        list_id=list_id,
                        item_id=it["id"],
                        done=e.value,
                        expected_slug=list_slug,
                    )
                except ListUnavailable:
                    if on_unavailable:
                        on_unavailable()
                    return
                broadcast_updates()

            checkbox.on_value_change(toggle)

            # Right side: Stepper (aligned right after name), Tags, Delete
            with ui.row().classes("shrink-0 items-center no-wrap gap-1"):
                qty = item.get("quantity", 1)
                should_show_counter = show_counters and (not only_gt_1 or qty > 1)
                if should_show_counter:

                    def change_qty(delta: int, it=item):
                        if is_active and not is_active():
                            return
                        try:
                            change_item_quantity(
                                list_id, it["id"], delta, expected_slug=list_slug
                            )
                        except ListUnavailable:
                            if on_unavailable:
                                on_unavailable()
                            return
                        broadcast_updates()

                    with ui.row().classes(
                        "items-center no-wrap gap-0.5 bg-slate-100 rounded px-1 py-0.5 mr-1"
                    ):
                        ui.button(
                            "-", on_click=lambda _e, it=item: change_qty(-1, it)
                        ).props("flat round dense size=xs color=grey-8").classes(
                            "w-4 h-4 p-0 min-w-0 min-h-0"
                        )
                        ui.label(str(item.get("quantity", 1))).classes(
                            "text-xs font-bold text-slate-700 min-w-[14px] text-center"
                        )
                        ui.button(
                            "+", on_click=lambda _e, it=item: change_qty(1, it)
                        ).props("flat round dense size=xs color=grey-8").classes(
                            "w-4 h-4 p-0 min-w-0 min-h-0"
                        )

                if quick_tags_active:
                    with ui.row().classes("items-center no-wrap gap-1 mx-1"):
                        for idx, tag in enumerate(list_tags):
                            color = TAG_COLORS[idx % len(TAG_COLORS)]
                            first_letter = tag[0].upper() if tag else "?"
                            is_tag_active = tag in item["active_tags"]

                            def toggle_tag(it=item, t=tag):
                                if is_active and not is_active():
                                    return
                                active = it["active_tags"].copy()
                                if t in active:
                                    active.remove(t)
                                else:
                                    active.append(t)
                                try:
                                    update_item_active_tags(
                                        it["id"],
                                        list_id,
                                        active,
                                        expected_slug=list_slug,
                                    )
                                except ListUnavailable:
                                    if on_unavailable:
                                        on_unavailable()
                                    return
                                broadcast_updates()

                            btn = ui.button(first_letter, on_click=toggle_tag)
                            btn_props = f"round size=12px dense color={color}"
                            if not is_tag_active:
                                btn_props += " outline"
                            btn.props(btn_props)
                if is_edit_mode:
                    ui.button(icon="delete", on_click=delete).props(
                        "flat round dense size=sm color=negative"
                    ).style("margin: -2px")


async def _add_theme_toggle() -> None:
    """Apply and remember this browser's theme without sharing it between users."""
    saved_theme = None
    try:
        ui.context.client.request  # Isolated UI tests have no browser request.
    except RuntimeError:
        saved_theme = None
    else:
        try:
            saved_theme = await ui.run_javascript(
                "return localStorage.getItem('listapp_theme')", timeout=3.0
            )
        except Exception:  # noqa: BLE001 - browser storage can be unavailable.
            saved_theme = None
    dark = ui.dark_mode(value=saved_theme == "dark")

    async def change_theme() -> None:
        dark.toggle()
        try:
            await ui.run_javascript(
                f"localStorage.setItem('listapp_theme', {json.dumps('dark' if dark.value else 'light')})",
                timeout=3.0,
            )
        except Exception:  # noqa: BLE001 - browser storage can be unavailable.
            ui.notify("Theme could not be saved on this device", color="warning")

    ui.button(icon="dark_mode", on_click=change_theme).props(
        "flat round aria-label='Toggle dark mode'"
    ).classes("fixed top-2 right-2 z-50").tooltip("Toggle light / dark mode")


@ui.page("/admin/login")
async def admin_login() -> None:
    _add_install_manifest()
    await _add_theme_toggle()

    def try_login() -> None:
        if password.value == GLOBAL_APP_PASSWORD:
            app.storage.user.update({"authenticated": True})
            ui.navigate.to("/admin")
        else:
            ui.notify("Wrong password", color="negative", position=NOTIFY_POSITION)

    with ui.card().classes("absolute-center"):
        ui.label("Enter Admin Password").classes("text-xl font-bold")
        password = (
            ui.input("Admin Password", password=True, password_toggle_button=True)
            .classes("w-full")
            .on("keydown.enter", try_login)
        )
        ui.button("Log in", on_click=try_login).classes("w-full mt-4")


@app.middleware("http")
async def auth_middleware(request, call_next):
    path = request.url.path
    if path == "/admin":
        is_authenticated = app.storage.user.get("authenticated", False)
        if not is_authenticated:
            from fastapi.responses import RedirectResponse

            return RedirectResponse("/admin/login")
    response = await call_next(request)
    if path == "/" or path.startswith(("/room/", "/list/", "/create-room/")):
        # These pages can contain UI personalized by ambient credentials.
        response.headers["Cache-Control"] = "no-store"
    if path.startswith("/create-room/"):
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@ui.refreshable
def room_list_ui() -> None:
    """Administrative room list; opening a room uses the explicit admin path."""
    if not app.storage.user.get("authenticated", False):
        return

    ui.button("Refresh rooms", icon="refresh", on_click=room_list_ui.refresh).props(
        "flat size=sm"
    )

    rooms = get_rooms()
    if not rooms:
        ui.label("No rooms yet. Create your first one!").classes("text-gray-500 italic")
        return

    for room in rooms:
        with (
            ui.card().classes("w-full mb-1 p-1"),
            ui.row().classes("w-full items-center no-wrap"),
        ):
            ui.button(
                room["name"],
                on_click=lambda slug=room["slug"]: ui.navigate.to(
                    f"/room/{slug}?admin=true"
                ),
            ).props("flat").classes("flex-grow text-left text-lg")

            def open_admin_reset_dialog(
                room_id=room["id"], room_name=room["name"]
            ) -> None:
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                    ui.label(f"Admin Reset: {room_name}").classes(
                        "text-lg font-bold text-red-500"
                    )
                    new_password_input = ui.input(
                        "New Room Password", password=True
                    ).classes("w-full")
                    with ui.row().classes("w-full justify-end mt-4"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        def submit() -> None:
                            if not app.storage.user.get("authenticated", False):
                                ui.notify("Admin sign-in required", color="negative")
                                return
                            if not new_password_input.value.strip():
                                ui.notify(
                                    "New password cannot be empty", color="warning"
                                )
                                return
                            update_room_password(room_id, new_password_input.value)
                            dialog.close()
                            ui.notify("Password reset successfully", color="positive")
                            room_list_ui.refresh()

                        ui.button("Reset", on_click=submit).props("color=negative")
                dialog.open()

            ui.button(icon="key", on_click=open_admin_reset_dialog).props(
                "flat round dense size=sm color=grey"
            )


@ui.page("/admin")
async def admin_page() -> None:
    _add_install_manifest()
    await _add_theme_toggle()
    with ui.card().classes("w-full max-w-sm mx-auto"):
        with ui.row().classes(
            "w-full items-center justify-between tracking-tighter mb-2"
        ):
            with ui.row().classes("items-center gap-0 text-3xl"):
                ui.label("List").classes("font-bold text-slate-800")
                ui.label("R").classes("font-black text-primary")

            def logout() -> None:
                app.storage.user.update({"authenticated": False})
                ui.navigate.to("/admin/login")

            ui.button("Log out", on_click=logout).props("flat size=sm")

        def open_new_room_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label("New Room").classes("text-lg font-bold")
                room_name_input = ui.input(label="Room name").classes("w-full")
                room_password_input = ui.input(label="Password", password=True).classes(
                    "w-full"
                )
                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def save() -> None:
                        if not app.storage.user.get("authenticated", False):
                            ui.notify("Admin sign-in required", color="negative")
                            return
                        try:
                            _new_id, new_slug = create_room(
                                room_name_input.value, room_password_input.value
                            )
                        except ValueError as error:
                            ui.notify(
                                str(error), color="warning", position=NOTIFY_POSITION
                            )
                            return
                        dialog.close()
                        ui.notify(
                            "Room created", color="positive", position=NOTIFY_POSITION
                        )
                        ui.navigate.to(f"/room/{new_slug}?admin=true")

                    ui.button("Create", on_click=save)
                room_password_input.on("keyup.enter", save)
            dialog.open()

        ui.button("Create New Room", icon="add", on_click=open_new_room_dialog).classes(
            "w-full mb-4"
        ).props("outline")

        room_list_ui()
        invitation_controls(
            lambda: bool(app.storage.user.get("authenticated", False)),
            str(ui.context.client.request.base_url),
        )


@ui.page("/create-room/{token}")
async def create_room_page(token: str) -> None:
    _add_install_manifest()
    await _add_theme_toggle()
    creation_form(token)


async def _room_access_from_browser(
    room_id: int, room_slug: str, admin_requested: bool
) -> tuple[RoomAccess, RoomAccessStatus]:
    """Load and validate a browser token without treating user storage as auth."""
    await _cleanup_legacy_room_password_keys()
    access = RoomAccess(
        room_id=room_id,
        room_slug=room_slug,
        token=None,
        admin_requested=admin_requested,
        admin_is_authenticated=lambda: bool(
            app.storage.user.get("authenticated", False)
        ),
    )
    storage_read, token = await _get_browser_storage(_room_token_storage_key(room_slug))
    if not storage_read:
        ui.notify(
            "Browser storage is unavailable. Room access cannot be remembered on this device.",
            color="warning",
            position=NOTIFY_POSITION,
        )
        return access, RoomAccessStatus.INVALID

    access = RoomAccess(
        room_id=room_id,
        room_slug=room_slug,
        token=token,
        admin_requested=False,
        admin_is_authenticated=lambda: False,
    )
    status = access.check()
    if status is RoomAccessStatus.VALID:
        _remember_authorized_room(room_slug)
    elif status is RoomAccessStatus.INVALID:
        _forget_authorized_room(room_slug)
        if token:
            await _remove_room_token(room_slug)
    return access, status


@ui.page("/")
async def index() -> None:
    _add_install_manifest()
    await _add_theme_toggle()
    await _cleanup_legacy_room_password_keys()
    storage_read, saved_last_room = await _get_browser_storage("listapp_last_room")
    if storage_read and saved_last_room:
        details = get_room_details_by_slug(saved_last_room)
        if details:
            token_storage_read, token = await _get_browser_storage(
                _room_token_storage_key(saved_last_room)
            )
            if not token_storage_read:
                ui.notify(
                    "Browser storage is unavailable. Room access cannot be remembered on this device.",
                    color="warning",
                    position=NOTIFY_POSITION,
                )
            else:
                access = RoomAccess(
                    room_id=details["id"],
                    room_slug=saved_last_room,
                    token=token,
                    admin_requested=False,
                    admin_is_authenticated=lambda: False,
                )
                status = access.check()
                if status is RoomAccessStatus.VALID:
                    _remember_authorized_room(saved_last_room)
                    ui.navigate.to(f"/room/{saved_last_room}")
                    return
                if status is RoomAccessStatus.INVALID:
                    _forget_authorized_room(saved_last_room)
                    if access.token:
                        await _remove_room_token(saved_last_room)
                    # Remembering a room is routing, not authorization. Its page
                    # still requires a valid token or prompts for the password.
                    ui.navigate.to(f"/room/{saved_last_room}")
                    return
                else:
                    ui.notify(
                        "Could not verify room access. Please retry; saved access was kept.",
                        color="warning",
                        position=NOTIFY_POSITION,
                    )
    elif not storage_read:
        ui.notify(
            "Browser storage is unavailable. Open your room link and sign in again.",
            color="warning",
            position=NOTIFY_POSITION,
        )

    with ui.card().classes("absolute-center w-full max-w-sm"):
        ui.label("Open your room link to continue").classes("text-xl font-bold mb-2")
        ui.label("Paste your room link or room code if needed.").classes(
            "text-sm text-gray-600 mb-2"
        )

        room_link_input = ui.input("Room link or code").classes("w-full")

        def go_to_room() -> None:
            raw_value = (room_link_input.value or "").strip()
            if not raw_value:
                ui.notify(
                    "Enter a room link or code",
                    color="warning",
                    position=NOTIFY_POSITION,
                )
                return

            try:
                room_slug = urlsplit(raw_value).path.rstrip("/").split("/")[-1]
            except ValueError:
                ui.notify("Invalid room link. Check the link/code.", color="negative")
                return
            if not get_room_details_by_slug(room_slug):
                ui.notify(
                    "Room not found. Check the link/code.",
                    color="negative",
                    position=NOTIFY_POSITION,
                )
                return

            app.storage.user.update({"last_room_slug": room_slug})
            ui.navigate.to(f"/room/{room_slug}")

        with ui.row().classes("w-full justify-end mt-2 gap-2"):
            ui.button("Open Room", on_click=go_to_room)
            ui.button("Admin", on_click=lambda: ui.navigate.to("/admin/login")).props(
                "outline"
            )

        room_link_input.on("keydown.enter", go_to_room)


@ui.page("/room/{slug}")
async def room_page(slug: str, admin: str | None = None) -> None:
    await _add_theme_toggle()
    details = get_room_details_by_slug(slug)
    _add_install_manifest(slug if details else None)
    if not details:
        ui.label("Room not found").classes("text-xl p-4")
        return

    room_id = details["id"]
    room_name = details["name"]
    admin_requested = admin == "true"
    access, access_status = await _room_access_from_browser(
        room_id, slug, admin_requested
    )
    if access_status is RoomAccessStatus.UNAVAILABLE:
        with ui.card().classes("absolute-center w-full max-w-sm"):
            ui.label("Could not verify room access.").classes("text-xl font-bold mb-2")
            ui.label("Please retry. Your saved access was kept.").classes(
                "text-sm text-gray-600"
            )
            ui.button("Retry", on_click=lambda: ui.navigate.to(f"/room/{slug}"))
        return

    if access_status is RoomAccessStatus.INVALID:
        with ui.card().classes("absolute-center w-full max-w-sm"):
            ui.label(f"Enter Room Password for {room_name}").classes(
                "text-xl font-bold mb-4"
            )
            password_input = ui.input("Room Password", password=True).classes("w-full")
            with ui.row().classes("w-full justify-end mt-4"):

                async def submit() -> None:
                    try:
                        issued = authenticate_room_and_issue_token(
                            slug, password_input.value
                        )
                    except Exception:  # noqa: BLE001 - a database failure must not clear storage.
                        ui.notify(
                            "Could not verify the password. Please retry.",
                            color="warning",
                            position=NOTIFY_POSITION,
                        )
                        return
                    if not issued:
                        ui.notify("Incorrect password", color="negative")
                        return

                    _issued_room_id, token = issued
                    if not await _store_room_access(slug, token):
                        revoke_room_access_token(slug, token)
                        ui.notify(
                            "Browser storage could not save access. It cannot be remembered on this device.",
                            color="warning",
                            position=NOTIFY_POSITION,
                        )
                        return
                    _remember_authorized_room(slug)
                    ui.navigate.to(f"/room/{slug}")

                ui.button("Enter", on_click=submit)
            password_input.on("keydown.enter", submit)
        return

    with ui.card().classes("w-full max-w-sm mx-auto"):
        with ui.row().classes(
            "w-full items-center justify-between flex-nowrap tracking-tighter mb-2"
        ):
            with ui.row().classes("items-center gap-2 flex-nowrap min-w-0 flex-1"):
                if access.is_admin():
                    ui.button(
                        icon="arrow_back", on_click=lambda: ui.navigate.to("/admin")
                    ).props("flat round dense")
                else:
                    with ui.row().classes(
                        "items-center gap-0 text-xl mr-1 flex-nowrap shrink-0"
                    ):
                        ui.label("List").classes("font-bold text-slate-800")
                        ui.label("R").classes("font-black text-primary")
                ui.label(room_name).classes(
                    "font-bold text-slate-800 text-2xl truncate min-w-0"
                )

            with (
                ui.button(icon="more_vert").props(
                    'flat round dense aria-label="Room menu"'
                ),
                ui.menu(),
            ):
                share_button(f"/room/{slug}", kind="room", as_menu_item=True)
                install_help_menu_item()
                ui.separator()
                ui.menu_item(
                    "Rename Room",
                    on_click=lambda: rename_room_dialog(room_id, room_name, slug),
                )
                ui.menu_item(
                    "Change Password",
                    on_click=lambda: change_password_dialog(slug),
                )
                ui.menu_item(
                    "Delete Room",
                    on_click=lambda: delete_room_dialog(slug),
                ).classes("text-red-500")

        def change_password_dialog(room_slug: str) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label("Change Room Password").classes("text-lg font-bold")
                old_password_input = ui.input(
                    "Current Password", password=True
                ).classes("w-full")
                new_password_input = ui.input("New Password", password=True).classes(
                    "w-full"
                )
                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    async def submit() -> None:
                        if not await _require_private_room_access(access):
                            return
                        if not new_password_input.value.strip():
                            ui.notify("New password cannot be empty", color="warning")
                            return
                        try:
                            changed = change_room_password_and_issue_token(
                                room_slug,
                                old_password_input.value,
                                new_password_input.value,
                            )
                        except Exception:  # noqa: BLE001 - do not erase credentials on database failure.
                            ui.notify(
                                "Could not change the password. Please retry.",
                                color="warning",
                                position=NOTIFY_POSITION,
                            )
                            return
                        if not changed:
                            ui.notify("Incorrect current password", color="negative")
                            return

                        _changed_room_id, new_token = changed
                        if not await _store_room_access(room_slug, new_token):
                            revoke_room_access_token(room_slug, new_token)
                            ui.notify(
                                "Password changed, but browser storage could not save access. Sign in with the new password.",
                                color="warning",
                                position=NOTIFY_POSITION,
                            )
                            ui.navigate.to(f"/room/{room_slug}")
                            return
                        _remember_authorized_room(room_slug)
                        dialog.close()
                        ui.notify("Password changed successfully", color="positive")
                        ui.navigate.to(f"/room/{room_slug}")

                    ui.button("Change", on_click=submit)
            dialog.open()

        def rename_room_dialog(
            target_room_id: int, current_name: str, room_slug: str
        ) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label("Rename Room").classes("text-lg font-bold")
                new_name_input = ui.input(value=current_name, label="New name").classes(
                    "w-full"
                )
                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    async def save() -> None:
                        if not await _require_private_room_access(access):
                            return
                        name = new_name_input.value.strip()
                        if not name:
                            ui.notify("Name cannot be empty", color="warning")
                            return
                        try:
                            if access.is_admin():
                                rename_room(target_room_id, name)
                            else:
                                rename_room_with_room_token(
                                    room_slug, access.token or "", name
                                )
                        except RoomAccessDenied:
                            await _require_private_room_access(access)
                            return
                        dialog.close()
                        ui.navigate.to(f"/room/{room_slug}")

                    ui.button("Save", on_click=save)
            dialog.open()

        def delete_room_dialog(room_slug: str) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label("Delete Room").classes("text-lg font-bold text-red-500")
                ui.label(
                    "Warning: This will delete ALL lists and items inside this room. This cannot be undone."
                ).classes("text-sm text-gray-600 mb-2")
                password_input = ui.input(
                    "Enter Room Password to Confirm", password=True
                ).classes("w-full")
                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    async def confirm() -> None:
                        if not await _require_private_room_access(access):
                            return
                        if not delete_room_with_password(
                            room_slug, password_input.value
                        ):
                            ui.notify("Incorrect password", color="negative")
                            return
                        dialog.close()
                        _forget_authorized_room(room_slug)
                        await _remove_room_token(room_slug)
                        ui.notify("Room deleted", color="negative")
                        ui.navigate.to("/admin" if access.is_admin() else "/")

                    ui.button("Delete", on_click=confirm).props("color=negative")
            dialog.open()

        def open_new_list_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
                ui.label("New List").classes("text-lg font-bold")
                list_name_input = ui.input(label="List name").classes("w-full")
                with ui.row().classes("w-full justify-end mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    async def save() -> None:
                        if not await _require_private_room_access(access):
                            return
                        try:
                            if access.is_admin():
                                _new_id, new_slug = create_list(
                                    list_name_input.value, room_id
                                )
                            else:
                                _new_id, new_slug = create_list_with_room_token(
                                    slug, access.token or "", list_name_input.value
                                )
                        except RoomAccessDenied:
                            await _require_private_room_access(access)
                            return
                        except ValueError:
                            ui.notify(
                                "Name cannot be empty",
                                color="warning",
                                position=NOTIFY_POSITION,
                            )
                            return
                        dialog.close()
                        ui.notify(
                            "List created", color="positive", position=NOTIFY_POSITION
                        )
                        ui.navigate.to(f"/list/{new_slug}")
                        broadcast_updates()

                    ui.button("Save", on_click=save)
                list_name_input.on("keyup.enter", save)
            dialog.open()

        ui.button("Add New List", icon="add", on_click=open_new_list_dialog).classes(
            "w-full mb-4"
        ).props("outline")
        list_of_lists(room_id=room_id, room_slug=slug, access=access)


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


def _restore_pending_undo(
    list_id: int, current: PendingUndo, *, list_slug: str
) -> None:
    if current["kind"] == "item":
        payload = current["payload"]
        restored = restore_deleted_item(
            list_id=list_id,
            name=payload["name"],
            done=payload["done"],
            active_tags=payload["active_tags"],
            description=payload["description"],
            quantity=payload["quantity"],
            expected_slug=list_slug,
        )
        if not restored:
            ui.notify(
                "Cannot undo: item name already exists",
                color="warning",
                position=NOTIFY_POSITION,
            )
            return

        ui.notify(
            f"Restored {payload['name']}",
            color="positive",
            position=NOTIFY_POSITION,
        )
        return

    payload = current["payload"]
    details_now = get_list_details(list_id)
    if not details_now or not list_identity_matches(details_now, list_slug):
        raise ListUnavailable(f"List {list_id} is no longer available")

    tags_now = details_now["list_tags"] or []
    if payload["tag"] not in tags_now:
        tags_now.append(payload["tag"])
    tags_now = sorted(tags_now, key=str.lower)
    update_list_tags_settings(list_id, tags_now, expected_slug=list_slug)
    ui.notify(
        f"Restored tag {payload['tag']}",
        color="positive",
        position=NOTIFY_POSITION,
    )


def _render_unavailable_list(
    state: ListPageState,
    on_back_to_room: Callable[[], None],
    *,
    message: str | None = None,
) -> None:
    with ui.column().classes(
        "w-full flex-grow items-center justify-center gap-3 p-6 text-center"
    ):
        ui.icon("error_outline", size="3rem").classes("text-slate-400")
        ui.label(
            message or _unavailable_list_message(state["room_authorized"])
        ).classes("text-lg text-slate-700")
        if state["room_authorized"] and state["room_slug"]:
            ui.button("Back to room", on_click=on_back_to_room).props("outline")


def _render_header(
    list_name: str,
    list_slug: str,
    room_authorized: bool,
    state: ViewState,
    undo_bar,
    tags_ui,
    room_slug: str,
    is_active: Callable[[], bool],
) -> None:
    with ui.column().classes("w-full mb-2 gap-1"):
        with ui.row().classes("w-full items-center justify-between"):
            if room_authorized:
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to(f"/room/{room_slug}"),
                ).props("flat round")
            else:
                with ui.row().classes("items-center gap-0 text-xl mr-1"):
                    ui.label("List").classes("font-bold text-slate-800")
                    ui.label("R").classes("font-black text-primary")

            with ui.row().classes("items-center gap-1"):
                details = get_list_details_by_identity(list_slug)
                if details:
                    share_button(f"/share/{details['share_token']}", kind="list")
                edit_btn_text = "Done" if state["edit_mode"] else "Options"

                def toggle_edit_mode() -> None:
                    if not is_active():
                        return
                    state.update({"edit_mode": not state["edit_mode"]})
                    undo_bar.refresh()
                    tags_ui.refresh()
                    item_list.refresh()

                ui.button(edit_btn_text, on_click=toggle_edit_mode).props("flat")

        ui.label(list_name).classes("text-2xl font-bold w-full truncate")


def _render_add_item_row(
    list_id: int,
    list_slug: str,
    is_active: Callable[[], bool],
    on_unavailable: Callable[[], None],
) -> None:
    with ui.row().classes("w-full items-center no-wrap gap-2 mt-2"):
        search_input = ui.input(label="Add or Search").classes("flex-grow")

        with search_input:
            menu = ui.menu().props(
                "fit no-focus no-refocus auto-close=false no-parent-event"
            )

        def submit(item_text: str | None = None) -> None:
            if not is_active():
                return
            to_add = normalize_item_name(
                item_text if item_text is not None else search_input.value or ""
            )
            if not to_add:
                return

            try:
                status, name = add_or_restore_item(
                    list_id, to_add, expected_slug=list_slug
                )
            except ListUnavailable:
                on_unavailable()
                return
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

            search_input.value = ""
            menu.close()
            search_input.run_method("focus")
            broadcast_updates()

        ui.button("Add", on_click=lambda: submit())

    def update_suggestions() -> None:
        if not is_active():
            return
        typed = normalize_item_name(search_input.value or "")
        menu.clear()
        if len(typed) < 1:
            menu.close()
            return

        lookup = _list_lookup_status(list_slug)
        if lookup != "exists":
            menu.close()
            if lookup == "missing":
                on_unavailable()
            return
        _, history = get_list_data(list_id)
        matches = [n for n in history if typed in n.lower()]
        if not matches:
            menu.close()
            return

        with menu:
            for item_name in matches[:3]:
                ui.menu_item(
                    item_name,
                    on_click=lambda name=item_name: submit(name),
                )
        menu.open()

    search_input.on_value_change(update_suggestions)
    search_input.on("focus", update_suggestions)
    search_input.on(
        "keydown.down",
        lambda: ui.run_javascript(
            """
            const first = document.querySelector(".q-menu .q-item");
            if (first) {
                first.focus();
                const menuEl = first.closest(".q-menu");
                if (menuEl && !menuEl.dataset.navBound) {
                    menuEl.dataset.navBound = "true";
                    menuEl.addEventListener("keydown", (e) => {
                        if (e.key === "ArrowDown" && document.activeElement?.nextElementSibling) {
                            e.preventDefault();
                            document.activeElement.nextElementSibling.focus();
                        } else if (e.key === "ArrowUp") {
                            e.preventDefault();
                            if (document.activeElement?.previousElementSibling) {
                                document.activeElement.previousElementSibling.focus();
                            } else {
                                const input = document.querySelector(".q-field input");
                                if (input) input.focus();
                            }
                        }
                    });
                }
            }
        """
        ),
    )
    search_input.on("keyup.enter", lambda: submit())


def _create_undo_bar(
    list_id: int,
    list_slug: str,
    state: ViewState,
    clear_pending_undo,
    tags_ui,
    is_active: Callable[[], bool],
    on_unavailable: Callable[[], None],
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
                if not is_active():
                    return
                current = state["pending_undo"]
                if not current or current["token"] != pending["token"]:
                    return

                try:
                    _restore_pending_undo(list_id, current, list_slug=list_slug)
                except ListUnavailable:
                    on_unavailable()
                    return
                clear_pending_undo()
                tags_ui.refresh()
                item_list.refresh()
                broadcast_updates()

            ui.button("Undo", on_click=undo).props("flat color=primary")

    return undo_bar


def _create_tags_ui(
    list_id: int,
    list_slug: str,
    state: ViewState,
    set_pending_undo,
    is_active: Callable[[], bool],
    on_unavailable: Callable[[], None],
):
    @ui.refreshable
    def tags_ui():
        if not is_active():
            return
        curr_details = get_list_details(list_id)
        if curr_details is None or not list_identity_matches(curr_details, list_slug):
            ui.timer(0.0, on_unavailable, once=True)
            return
        list_tags = sorted(curr_details["list_tags"], key=str.lower)
        quick_tags_active = len(list_tags) > 0

        if state["edit_mode"]:
            with ui.column().classes(
                "w-full mt-2 p-3 bg-slate-50 border border-slate-200 rounded gap-2"
            ):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Show quantities").classes(
                        "text-sm font-medium text-slate-700"
                    )
                    show_qty_switch = ui.switch(
                        value=state.get("show_counters", False)
                    ).props("dense")

                    def toggle_qty(e):
                        state["show_counters"] = e.value
                        tags_ui.refresh()
                        item_list.refresh()

                    show_qty_switch.on_value_change(toggle_qty)

                if state.get("show_counters", False):
                    with ui.row().classes(
                        "w-full items-center justify-between pl-3 border-t border-slate-200 pt-1.5"
                    ):
                        ui.label("Only show minimum 2").classes(
                            "text-sm text-slate-600"
                        )
                        gt_1_switch = ui.switch(
                            value=state.get("only_gt_1", False)
                        ).props("dense")

                        def toggle_gt_1(e):
                            state["only_gt_1"] = e.value
                            item_list.refresh()

                        gt_1_switch.on_value_change(toggle_gt_1)

            with ui.row().classes("w-full items-center mt-2 gap-2"):
                new_tag_input = ui.input("Add Tag").classes("flex-grow")

                def add_tag() -> None:
                    if not is_active():
                        return
                    tag = new_tag_input.value.strip()
                    if tag and tag not in list_tags:
                        updated_tags = sorted([*list_tags, tag], key=str.lower)
                        try:
                            update_list_tags_settings(
                                list_id, updated_tags, expected_slug=list_slug
                            )
                        except ListUnavailable:
                            on_unavailable()
                            return
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
                    is_filter_active = state["filter_tag"] == tag

                    def toggle_filter(t=tag) -> None:
                        if not is_active():
                            return
                        if state["filter_tag"] == t:
                            state["filter_tag"] = None
                        else:
                            state["filter_tag"] = t
                        tags_ui.refresh()
                        item_list.refresh()

                    def delete_tag(t=tag) -> None:
                        if not is_active():
                            return
                        if t in list_tags:
                            updated_tags = [x for x in list_tags if x != t]
                            try:
                                update_list_tags_settings(
                                    list_id, updated_tags, expected_slug=list_slug
                                )
                            except ListUnavailable:
                                on_unavailable()
                                return
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
                        if not is_filter_active:
                            btn_props += " outline"
                        btn.props(btn_props).classes("px-2")

                        if state["edit_mode"]:
                            del_btn = ui.button(icon="close", on_click=delete_tag)
                            del_btn_props = f"rounded size=sm color={color} flat dense"
                            del_btn.props(del_btn_props)

    return tags_ui


def _delete_item_with_undo(
    list_id: int,
    list_slug: str,
    it: dict,
    set_pending_undo,
    is_active: Callable[[], bool],
    on_unavailable: Callable[[], None],
) -> None:
    if not is_active():
        return
    payload: ItemUndoPayload = {
        "name": it["name"],
        "done": it["done"],
        "active_tags": it["active_tags"].copy(),
        "description": it["description"],
        "quantity": it["quantity"],
    }
    try:
        delete_item_from_list(list_id, it["id"], expected_slug=list_slug)
    except ListUnavailable:
        on_unavailable()
        return
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


@ui.page("/list/{slug}")
async def list_page(slug: str):
    await _list_page(slug, public=False)


@ui.page("/share/{token}")
async def shared_list_page(token: str):
    await _list_page(f"share:{token}", public=True)


async def _list_page(slug: str, *, public: bool):
    _add_install_manifest()
    await _add_theme_toggle()
    ui.add_head_html('<meta name="referrer" content="no-referrer">')
    page_url = f"/share/{slug.removeprefix('share:')}" if public else f"/list/{slug}"
    try:
        details = (
            get_list_details_by_identity(slug)
            if public
            else get_list_details_by_slug(slug)
        )
    except sqlite3.Error:
        with (
            ui.card()
            .classes("w-full max-w-sm mx-auto")
            .style(
                "height: 100dvh; display: flex; flex-direction: column; min-height: 0;"
            ),
            ui.column().classes(
                "w-full flex-grow items-center justify-center gap-3 p-6 text-center"
            ),
        ):
            ui.label("Could not load this list. Please retry.").classes(
                "text-lg text-slate-700"
            )
            ui.button("Retry", on_click=lambda: ui.navigate.to(page_url)).props(
                "outline"
            )
        return

    if not details:
        missing_state: ListPageState = {
            "status": "unavailable",
            "list_id": None,
            "list_slug": slug,
            "list_name": None,
            "room_slug": None,
            "room_authorized": False,
        }
        with (
            ui.card()
            .classes("w-full max-w-sm mx-auto")
            .style(
                "height: 100dvh; display: flex; flex-direction: column; min-height: 0;"
            ),
            ui.column().classes("w-full flex-grow min-h-0"),
        ):
            _render_unavailable_list(missing_state, lambda: None)
        return

    list_id = details["id"]
    room_slug = details["room_slug"]

    await _cleanup_legacy_room_password_keys()
    storage_read, token = await _get_browser_storage(_room_token_storage_key(room_slug))
    room_access = RoomAccess(
        room_id=details["room_id"],
        room_slug=room_slug,
        token=token if storage_read else None,
        admin_requested=False,
        admin_is_authenticated=lambda: False,
    )
    room_authorized = False
    if storage_read:
        access_status = room_access.check()
        if access_status is RoomAccessStatus.VALID:
            room_authorized = True
            _remember_authorized_room(room_slug)
        elif access_status is RoomAccessStatus.INVALID:
            _forget_authorized_room(room_slug)
            if token:
                await _remove_room_token(room_slug)

    # Legacy slug URLs never disclose tokens or list content without room access.
    if not public and not room_authorized:
        ui.label("Room access required to open this list.")
        ui.button("Open room", on_click=lambda: ui.navigate.to(f"/room/{room_slug}"))
        return

    page_state: ListPageState = {
        "status": "active",
        "list_id": list_id,
        "list_slug": slug,
        "list_name": details["name"],
        "room_slug": room_slug,
        "room_authorized": room_authorized,
    }
    view_state: ViewState = {
        "filter_tag": None,
        "edit_mode": False,
        "pending_undo": None,
        "focus_tag_input": False,
        "show_counters": False,
        "only_gt_1": False,
    }
    availability_timer = None
    active_content = None

    def is_active() -> bool:
        if page_state["status"] != "active":
            return False
        if not public and room_access.check() is not RoomAccessStatus.VALID:
            ui.timer(0.0, transition_to_unavailable, once=True)
            return False
        lookup = _list_lookup_status(slug)
        if lookup == "missing":
            # Refreshable children must finish before replacing their parent.
            ui.timer(0.0, transition_to_unavailable, once=True)
            return False
        return lookup == "exists"

    def transition_to_unavailable() -> None:
        nonlocal availability_timer
        if not _transition_list_state(page_state):
            return
        if availability_timer is not None:
            with suppress(Exception):
                availability_timer.cancel()
            availability_timer = None

        try:
            room_exists = get_room_details_by_slug(room_slug) is not None
        except sqlite3.Error:
            room_exists = False
        page_state["room_authorized"] = _can_return_to_room(
            room_access.check(), room_exists
        )

        if active_content is not None:
            active_content.clear()
            with active_content:
                _render_unavailable_list(
                    page_state,
                    go_back_to_room,
                    message="This list was deleted or this share link was reset."
                    if public
                    else None,
                )

    def go_back_to_room() -> None:
        if page_state["room_authorized"]:
            ui.navigate.to(f"/room/{room_slug}")

    def set_pending_undo(action: PendingUndoInput) -> None:
        if not is_active():
            return
        token = str(uuid.uuid4())
        view_state["pending_undo"] = _build_pending_undo(action, token)
        undo_bar.refresh()

        def expire() -> None:
            current_pending = view_state["pending_undo"]
            if current_pending and current_pending["token"] == token:
                view_state["pending_undo"] = None
                if is_active():
                    undo_bar.refresh()

        ui.timer(5.0, expire, once=True)

    def clear_pending_undo() -> None:
        view_state["pending_undo"] = None
        if is_active():
            undo_bar.refresh()

    def poll_list_existence() -> None:
        if not is_active():
            return
        if _list_lookup_status(slug) == "missing":
            transition_to_unavailable()

    with (
        ui.card()
        .classes("w-full max-w-sm mx-auto")
        .style("height: 100dvh; display: flex; flex-direction: column; min-height: 0;")
    ):
        active_content = ui.column().classes("w-full flex-grow min-h-0")
        with active_content:
            tags_ui = _create_tags_ui(
                list_id=list_id,
                list_slug=slug,
                state=view_state,
                set_pending_undo=set_pending_undo,
                is_active=is_active,
                on_unavailable=transition_to_unavailable,
            )
            undo_bar = _create_undo_bar(
                list_id=list_id,
                list_slug=slug,
                state=view_state,
                clear_pending_undo=clear_pending_undo,
                tags_ui=tags_ui,
                is_active=is_active,
                on_unavailable=transition_to_unavailable,
            )

            _render_header(
                list_name=details["name"],
                list_slug=slug,
                room_authorized=room_authorized,
                state=view_state,
                undo_bar=undo_bar,
                tags_ui=tags_ui,
                room_slug=room_slug,
                is_active=is_active,
            )
            if room_authorized:

                def confirm_reset_share_link() -> None:
                    with ui.dialog() as dialog, ui.card():
                        ui.label("Reset share link?")
                        ui.label(
                            "Everyone using the old link will lose access. Room access stays unchanged."
                        )

                        def reset() -> None:
                            try:
                                rotate_list_share_token(
                                    room_slug,
                                    room_access.token or "",
                                    list_id,
                                    expected_slug=details["slug"],
                                )
                            except (PermissionError, ListUnavailable):
                                ui.notify(
                                    "Room access required or list unavailable.",
                                    type="negative",
                                )
                                dialog.close()
                                return
                            except sqlite3.Error:
                                ui.notify(
                                    "Could not reset the link. Please retry.",
                                    type="negative",
                                )
                                return
                            dialog.close()
                            broadcast_updates()
                            ui.navigate.to(f"/list/{details['slug']}")

                        ui.button("Cancel", on_click=dialog.close)
                        ui.button("Reset share link", on_click=reset)
                    dialog.open()

                ui.button("Reset share link", on_click=confirm_reset_share_link).props(
                    "flat"
                )
            undo_bar()
            tags_ui()
            _render_add_item_row(
                list_id=list_id,
                list_slug=slug,
                is_active=is_active,
                on_unavailable=transition_to_unavailable,
            )

            with (
                ui.element("div")
                .classes("w-full")
                .style("flex: 1 1 auto; min-height: 0; overflow-y: auto;")
            ):
                item_list(
                    list_id,
                    lambda: view_state["filter_tag"],
                    lambda: view_state["edit_mode"],
                    lambda it: _delete_item_with_undo(
                        list_id,
                        slug,
                        it,
                        set_pending_undo,
                        is_active,
                        transition_to_unavailable,
                    ),
                    lambda: view_state.get("show_counters", False),
                    lambda: view_state.get("only_gt_1", False),
                    is_active,
                    transition_to_unavailable,
                    list_slug=slug,
                )

        availability_timer = ui.timer(2.0, poll_list_existence)


if __name__ in {"__main__", "__mp_main__"}:
    import argparse

    parser = argparse.ArgumentParser(description="ListR Web App")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8080")),
        help="Port to run the app on",
    )
    args, _ = parser.parse_known_args()
    port = args.port
    ui.run(
        host="0.0.0.0",
        port=port,
        reload=app_reload_enabled(),
        title="ListR",
        favicon="/static/icons/favicon-32.png",
        storage_secret=os.environ["NICEGUI_STORAGE_SECRET"],
    )
