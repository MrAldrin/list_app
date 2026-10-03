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
    create_or_find_list_locked,
    delete_list_locked,
    get_list_uid_locked,
    get_room_seq_locked,
    list_id_for_uid_locked,
    normalize_display_name,
    rename_list_if_unique_locked,
    savepoint_locked,
    uid_in_use_locked,
)
from live_updates import notify_room_changed

router = APIRouter()


def _canonical_uuid(value: str) -> str:
    return str(uuid.UUID(value))


# A UUID string in its lowercase, hyphenated form.
Uuid = Annotated[StrictStr, AfterValidator(_canonical_uuid)]


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
    base_seq: Annotated[StrictInt, Field(ge=0)]


class ListDelete(Op):
    type: Literal["list.delete"]
    list_uid: Uuid


AnyOp = Annotated[ListCreate | ListRename | ListDelete, Field(discriminator="type")]
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
EMPTY_NAME = "Name cannot be empty"


def _room_list_id(room_id: int, list_uid: str) -> int:
    list_id = list_id_for_uid_locked(room_id, list_uid)
    if list_id is None:
        # Deleted, or in another room: the client cannot tell which.
        raise OpRejected("list_unavailable", LIST_UNAVAILABLE)
    return list_id


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


HANDLERS: dict[str, Callable[[int, Any], dict[str, Any]]] = {
    "list.create": list_create,
    "list.rename": list_rename,
    "list.delete": list_delete,
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
