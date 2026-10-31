"""Online-only management of the room's named item groups."""

import sqlite3
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import StrictInt, StrictStr

from api.access import room_access
from api.errors import ApiError
from api.requests import ItemGroupJsonBody, JsonBody, StrictBody, parse_body
from database_crud import (
    CountLimitReached,
    ItemGroupNameTaken,
    create_item_group_locked,
    delete_item_group_locked,
    get_room_seq_locked,
    normalize_display_name,
    normalize_item_name,
    update_item_group_locked,
)
from field_limits import MAX_ITEMS_PER_GROUP, MAX_NAME_LENGTH
from identifiers import canonical_uuid
from item_names import item_name_key
from live_updates import notify_room_changed

router = APIRouter()


class ItemGroupFields(StrictBody):
    name: StrictStr
    items: list[StrictStr]


class ItemGroupUpdate(ItemGroupFields):
    base_seq: StrictInt


class ItemGroupDelete(StrictBody):
    base_seq: StrictInt


def _group_name(raw: str) -> str:
    name = normalize_display_name(raw)
    if not name:
        raise ApiError(422, "invalid_request", "Group name cannot be empty.")
    if len(name) > MAX_NAME_LENGTH:
        raise ApiError(
            422,
            "invalid_request",
            f"Group name can be at most {MAX_NAME_LENGTH} characters.",
        )
    return name


def _group_items(raw_items: list[str]) -> list[str]:
    if len(raw_items) > MAX_ITEMS_PER_GROUP:
        raise ApiError(
            422,
            "invalid_request",
            f"A group can contain at most {MAX_ITEMS_PER_GROUP} items.",
        )
    normalized: list[str] = []
    keys: set[str] = set()
    for raw in raw_items:
        name = normalize_item_name(raw)
        if not name:
            raise ApiError(422, "invalid_request", "Group item names cannot be empty.")
        if len(name) > MAX_NAME_LENGTH:
            raise ApiError(
                422,
                "invalid_request",
                f"Group item names can be at most {MAX_NAME_LENGTH} characters.",
            )
        key = item_name_key(name)
        if key in keys:
            raise ApiError(
                422,
                "invalid_request",
                "A group cannot contain the same item more than once.",
            )
        keys.add(key)
        normalized.append(name)
    return normalized


def _group_uid(raw: str) -> str:
    try:
        return canonical_uuid(raw)
    except (ValueError, AttributeError):
        raise ApiError(422, "invalid_request") from None


def _write_error(error: Exception) -> ApiError:
    if isinstance(error, ItemGroupNameTaken):
        return ApiError(
            409, "group_name_taken", "A group with that name already exists."
        )
    if isinstance(error, CountLimitReached):
        return ApiError(422, "invalid_request", str(error))
    if isinstance(error, sqlite3.Error):
        return ApiError(503, "unavailable")
    raise error


@router.post("/rooms/{slug}/item-groups", status_code=201)
def create_item_group(
    slug: str, request: Request, body: ItemGroupJsonBody
) -> dict[str, Any]:
    data = parse_body(ItemGroupFields, body)
    name = _group_name(data.name)
    items = _group_items(data.items)
    try:
        with room_access(request, slug, write=True) as room:
            group = create_item_group_locked(room.room_id, name, items)
            room_id = room.room_id
    except (ItemGroupNameTaken, CountLimitReached, sqlite3.Error) as error:
        raise _write_error(error) from None
    notify_room_changed(room_id)
    return {"group": group}


@router.put("/rooms/{slug}/item-groups/{group_uid}")
def update_item_group(
    slug: str,
    group_uid: str,
    request: Request,
    body: ItemGroupJsonBody,
) -> dict[str, Any]:
    data = parse_body(ItemGroupUpdate, body)
    if data.base_seq < 0:
        raise ApiError(422, "invalid_request")
    name = _group_name(data.name)
    items = _group_items(data.items)
    uid = _group_uid(group_uid)
    try:
        with room_access(request, slug, write=True) as room:
            before = get_room_seq_locked(room.room_id)
            status, group = update_item_group_locked(
                room.room_id, uid, data.base_seq, name, items
            )
            room_id = room.room_id
            if status == "missing":
                raise ApiError(
                    404, "group_unavailable", "The group is no longer available."
                )
            if status == "changed":
                raise ApiError(
                    409,
                    "group_changed_meanwhile",
                    "Someone else changed this group. Reload it before saving.",
                )
            after = get_room_seq_locked(room.room_id)
    except (ItemGroupNameTaken, CountLimitReached, sqlite3.Error) as error:
        raise _write_error(error) from None
    if after != before:
        notify_room_changed(room_id)
    if group is None:
        raise RuntimeError("Updated item group could not be read")
    return {"group": group}


@router.delete("/rooms/{slug}/item-groups/{group_uid}", status_code=204)
def delete_item_group(
    slug: str,
    group_uid: str,
    request: Request,
    body: JsonBody,
) -> Response:
    data = parse_body(ItemGroupDelete, body)
    if data.base_seq < 0:
        raise ApiError(422, "invalid_request")
    uid = _group_uid(group_uid)
    try:
        with room_access(request, slug, write=True) as room:
            before = get_room_seq_locked(room.room_id)
            status = delete_item_group_locked(room.room_id, uid, data.base_seq)
            room_id = room.room_id
            if status == "missing":
                raise ApiError(
                    404, "group_unavailable", "The group is no longer available."
                )
            if status == "changed":
                raise ApiError(
                    409,
                    "group_changed_meanwhile",
                    "Someone else changed this group. Reload it before deleting.",
                )
            after = get_room_seq_locked(room.room_id)
    except sqlite3.Error as error:
        raise _write_error(error) from None
    if after != before:
        notify_room_changed(room_id)
    return Response(status_code=204)
