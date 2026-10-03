"""Write operations: `POST /api/v1/rooms/{slug}/ops` (docs/api.md, "Writing").

One operation per request. Each op type has a body model (picked by `type`)
and a handler that runs inside the room's write transaction. A handler
returns the `result`, or raises OpRejected when a business rule says no.
Rejected ops change nothing, but their response is stored like an applied
one, so a retry gets the same answer.
"""

import uuid
from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidationError,
)

from api.access import room_access
from api.errors import ApiError
from api.idempotency import Response, request_hash, run_once_locked
from api.requests import json_object
from database_crud import (
    add_or_restore_item_locked,
    adjust_item_quantity_locked,
    create_or_find_list_locked,
    delete_item_locked,
    delete_list_locked,
    get_item_uid_locked,
    get_list_uid_locked,
    get_room_seq_locked,
    item_id_for_uid_locked,
    list_id_for_uid_locked,
    normalize_completion_time,
    normalize_display_name,
    normalize_item_name,
    rename_list_if_unique_locked,
    restore_deleted_item_locked,
    savepoint_locked,
    uid_in_use_locked,
    update_item_details_locked,
    update_item_done_locked,
)
from item_service import STATUS_DUPLICATE_ACTIVE, clamp_quantity, normalize_item_details
from live_updates import notify_room_changed

router = APIRouter()


def _canonical_uuid(value: str) -> str:
    return str(uuid.UUID(value))


# A UUID string in its lowercase, hyphenated form.
Uuid = Annotated[StrictStr, AfterValidator(_canonical_uuid)]

# Bounds quantities and deltas far from SQLite's 64-bit integer limit.
MAX_QUANTITY = 1_000_000
# Below 1 is saved as 1, as in NiceGUI's edit dialog.
Quantity = Annotated[StrictInt, Field(ge=-MAX_QUANTITY, le=MAX_QUANTITY)]
BaseSeq = Annotated[StrictInt, Field(ge=0)]


def _completion_time(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_completion_time(value)
    if normalized is None:
        raise ValueError("completed_at is not a readable time")
    return normalized


# An ISO 8601 time, stored as UTC with Z.
CompletedAt = Annotated[StrictStr | None, AfterValidator(_completion_time)]


class Op(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op_id: Uuid


class ListCreate(Op):
    type: Literal["list.create"]
    name: StrictStr
    uid: Uuid | None = None


class ListRename(Op):
    type: Literal["list.rename"]
    list_uid: Uuid
    name: StrictStr
    # Required but not used yet: the last write wins until Milestone 6.
    base_seq: BaseSeq


class ListDelete(Op):
    type: Literal["list.delete"]
    list_uid: Uuid


class ItemAdd(Op):
    type: Literal["item.add"]
    list_uid: Uuid
    name: StrictStr
    uid: Uuid | None = None


class ItemOp(Op):
    list_uid: Uuid
    item_uid: Uuid


class ItemSetDone(ItemOp):
    type: Literal["item.set_done"]
    done: StrictBool


class ItemQuantityDelta(ItemOp):
    type: Literal["item.quantity_delta"]
    delta: Quantity


class ItemEdit(ItemOp):
    type: Literal["item.edit"]
    name: StrictStr
    description: StrictStr
    quantity: Quantity | None = None
    # Required but not used yet: the last write wins until Milestone 6.
    base_seq: BaseSeq


class ItemDelete(ItemOp):
    type: Literal["item.delete"]


class ItemRestore(Op):
    type: Literal["item.restore"]
    list_uid: Uuid
    uid: Uuid | None = None
    name: StrictStr
    done: StrictBool
    tags: list[StrictStr]
    description: StrictStr
    quantity: Quantity
    completed_at: CompletedAt


AnyOp = Annotated[
    ListCreate
    | ListRename
    | ListDelete
    | ItemAdd
    | ItemSetDone
    | ItemQuantityDelta
    | ItemEdit
    | ItemDelete
    | ItemRestore,
    Field(discriminator="type"),
]
_OPS = TypeAdapter(AnyOp)


def parse_op(data: dict[str, Any]) -> Op:
    """Validate an op body; unknown `type` or wrong fields give 422."""
    try:
        return _OPS.validate_python(data)
    except ValidationError:
        raise ApiError(422, "invalid_request") from None


class OpRejected(Exception):
    """A business rule said no. Shown to the user; nothing is changed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message


# Messages as NiceGUI shows them.
LIST_UNAVAILABLE = "The list is no longer available."
ITEM_NOT_FOUND = "The item is no longer available."
EMPTY_NAME = "Name cannot be empty"
UNDO_NAME_TAKEN = "Cannot undo: item name already exists"


def _room_list_id(room_id: int, list_uid: str) -> int:
    list_id = list_id_for_uid_locked(room_id, list_uid)
    if list_id is None:
        # Deleted, or in another room: the client cannot tell which.
        raise OpRejected("list_unavailable", LIST_UNAVAILABLE)
    return list_id


def _list_item_id(list_id: int, item_uid: str) -> int:
    item_id = item_id_for_uid_locked(list_id, item_uid)
    if item_id is None:
        # Deleted, or in another list.
        raise OpRejected("item_not_found", ITEM_NOT_FOUND)
    return item_id


def _item_found(matched: bool) -> None:
    if not matched:
        raise OpRejected("item_not_found", ITEM_NOT_FOUND)


def _item_name(raw: str) -> str:
    name = normalize_item_name(raw)
    if not name:
        raise OpRejected("invalid_name", EMPTY_NAME)
    return name


def _list_name(raw: str) -> str:
    name = normalize_display_name(raw)
    if not name:
        raise OpRejected("invalid_name", EMPTY_NAME)
    return name


def _new_uid(uid: str | None) -> str | None:
    if uid is not None and uid_in_use_locked(uid):
        raise ApiError(422, "invalid_request", "This uid is already used.")
    return uid


def list_create(room_id: int, op: ListCreate) -> dict[str, Any]:
    uid = _new_uid(op.uid)
    list_id, slug, created = create_or_find_list_locked(
        _list_name(op.name), room_id, uid=uid
    )
    return {"list_uid": get_list_uid_locked(list_id), "slug": slug, "created": created}


def list_rename(room_id: int, op: ListRename) -> dict[str, Any]:
    list_id = _room_list_id(room_id, op.list_uid)
    name = _list_name(op.name)
    if not rename_list_if_unique_locked(list_id, room_id, name):
        raise OpRejected("duplicate_name", f"'{name}' already exists in this room")
    return {}


def list_delete(room_id: int, op: ListDelete) -> dict[str, Any]:
    delete_list_locked(_room_list_id(room_id, op.list_uid))
    return {}


def item_add(room_id: int, op: ItemAdd) -> dict[str, Any]:
    uid = _new_uid(op.uid)
    list_id = _room_list_id(room_id, op.list_uid)
    name = _item_name(op.name)
    outcome, item_id = add_or_restore_item_locked(name, list_id, uid=uid)
    if outcome == STATUS_DUPLICATE_ACTIVE:
        raise OpRejected("duplicate_active", f"'{name}' is already on the list")
    return {"item_uid": get_item_uid_locked(item_id), "outcome": outcome}


def item_set_done(room_id: int, op: ItemSetDone) -> dict[str, Any]:
    list_id = _room_list_id(room_id, op.list_uid)
    item_id = _list_item_id(list_id, op.item_uid)
    _item_found(update_item_done_locked(item_id, list_id, op.done))
    return {}


def item_quantity_delta(room_id: int, op: ItemQuantityDelta) -> dict[str, Any]:
    list_id = _room_list_id(room_id, op.list_uid)
    item_id = _list_item_id(list_id, op.item_uid)
    _item_found(adjust_item_quantity_locked(item_id, list_id, op.delta))
    return {}


def item_edit(room_id: int, op: ItemEdit) -> dict[str, Any]:
    list_id = _room_list_id(room_id, op.list_uid)
    item_id = _list_item_id(list_id, op.item_uid)
    name, description, quantity = normalize_item_details(
        op.name, op.description, op.quantity
    )
    if not name:
        raise OpRejected("invalid_name", EMPTY_NAME)
    status = update_item_details_locked(item_id, list_id, name, description, quantity)
    if status == "duplicate":
        raise OpRejected("duplicate_name", f"'{name}' already exists")
    _item_found(status == "saved")
    return {}


def item_delete(room_id: int, op: ItemDelete) -> dict[str, Any]:
    list_id = _room_list_id(room_id, op.list_uid)
    item_id = item_id_for_uid_locked(list_id, op.item_uid)
    if item_id is not None:
        delete_item_locked(item_id, list_id)
    # Already gone (or in another list): nothing to do, not an error.
    return {}


def item_restore(room_id: int, op: ItemRestore) -> dict[str, Any]:
    uid = _new_uid(op.uid)
    list_id = _room_list_id(room_id, op.list_uid)
    item_id = restore_deleted_item_locked(
        list_id,
        _item_name(op.name),
        op.done,
        op.tags,
        op.description,
        clamp_quantity(op.quantity),
        completed_at=op.completed_at,
        uid=uid,
    )
    if item_id is None:
        raise OpRejected("undo_name_taken", UNDO_NAME_TAKEN)
    return {"item_uid": get_item_uid_locked(item_id)}


HANDLERS: dict[str, Callable[[int, Any], dict[str, Any]]] = {
    "list.create": list_create,
    "list.rename": list_rename,
    "list.delete": list_delete,
    "item.add": item_add,
    "item.set_done": item_set_done,
    "item.quantity_delta": item_quantity_delta,
    "item.edit": item_edit,
    "item.delete": item_delete,
    "item.restore": item_restore,
}


def _apply_locked(room_id: int, op: Any) -> Response:
    try:
        with savepoint_locked():
            result = HANDLERS[op.type](room_id, op)
    except OpRejected as rejection:
        return {
            "op_id": op.op_id,
            "status": "rejected",
            "code": rejection.code,
            "message": rejection.message,
            "seq": get_room_seq_locked(room_id),
        }
    return {
        "op_id": op.op_id,
        "status": "applied",
        "result": result,
        "seq": get_room_seq_locked(room_id),
    }


@router.post("/rooms/{slug}/ops")
def post_op(
    slug: str, request: Request, body: dict[str, Any] = Depends(json_object)
) -> Response:
    op = parse_op(body)
    body_hash = request_hash(op)
    with room_access(request, slug, write=True) as room:
        response, replayed = run_once_locked(
            room.room_id, op.op_id, body_hash, lambda: _apply_locked(room.room_id, op)
        )
    # After the commit, outside the database lock.
    if not replayed and response["status"] == "applied":
        notify_room_changed(room.room_id)
    return response
