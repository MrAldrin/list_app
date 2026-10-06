"""Public share links (docs/public-sharing.md, docs/api.md "Share links").

A share token opens one list for viewing and editing, without the room
password. It never gives room access: the share endpoints read and write only
that list, and the room endpoints still need the room cookie.

- Share holders: `GET /api/v1/share/{token}/changes`, `POST …/ops` and
  `GET …/events` (in `api/events.py`).
- Room members: read the link and reset it, under
  `/api/v1/rooms/{slug}/lists/{list_uid}/share-link`.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from api.access import room_access, room_token, share_access
from api.changes import MAX_SEQ
from api.errors import ApiError
from api.idempotency import Response
from api.ops import run_share_op
from api.requests import json_object, parse_body
from database_crud import (
    get_item_changes_locked,
    get_list_changes_locked,
    get_room_details_locked,
    get_room_seq_locked,
    get_share_token_locked,
    list_id_for_uid_locked,
    room_matches_token_locked,
    rotate_share_token_locked,
)
from live_updates import notify_room_changed

router = APIRouter()


def _room_for_member(request: Request, room_id: int) -> dict[str, str] | None:
    """The list's room, only when this request's room cookie grants access.

    The cookie's name holds the room slug, so the slug is read from the
    database first and then checked against the cookie in the same
    transaction. A stale or foreign cookie gives None.
    """
    details = get_room_details_locked(room_id)
    if details is None:
        return None
    token = room_token(request, details["slug"])
    if not room_matches_token_locked(details["slug"], room_id, token):
        return None
    return details


@router.get("/share/{token}/changes")
def share_changes(
    token: str, since: Annotated[int, Query(ge=0, le=MAX_SEQ)], request: Request
) -> dict[str, Any]:
    """The shared list and its items, always as a full snapshot.

    Deltas would need the room's deletion records, which also name items of
    other lists. One list is small, so `since` is checked but not used. The
    list's `slug` is left out: it is room navigation, not a public address.

    `room` is null, unless this browser's cookie for the list's room is valid
    right now: then it is the room's slug and name, so the page can offer
    "back to room" and "Reset share link". Anyone else learns nothing.
    """
    del since
    with share_access(token) as share:
        room = _room_for_member(request, share.room_id)
        lists = get_list_changes_locked(share.room_id, None, list_id=share.list_id)
        return {
            "seq": get_room_seq_locked(share.room_id),
            "full": True,
            "room": room,
            "lists": [{**row, "slug": ""} for row in lists],
            "items": get_item_changes_locked(
                share.room_id, None, list_id=share.list_id
            ),
            "deletions": [],
        }


@router.post("/share/{token}/ops")
def share_op(token: str, body: dict[str, Any] = Depends(json_object)) -> Response:
    return run_share_op(token, body)


class ResetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _room_list_id(room_id: int, list_uid: str) -> int:
    try:
        uid = str(uuid.UUID(list_uid))
    except ValueError:
        uid = None
    list_id = None if uid is None else list_id_for_uid_locked(room_id, uid)
    if list_id is None:
        # Deleted, or in another room: the same answer.
        raise ApiError(404, "list_unavailable")
    return list_id


@router.get("/rooms/{slug}/lists/{list_uid}/share-link")
def get_share_link(slug: str, list_uid: str, request: Request) -> dict[str, str]:
    """The list's share token, for room members only."""
    with room_access(request, slug) as room:
        return {"token": get_share_token_locked(_room_list_id(room.room_id, list_uid))}


@router.post("/rooms/{slug}/lists/{list_uid}/share-link")
def reset_share_link(
    slug: str,
    list_uid: str,
    request: Request,
    body: dict[str, Any] = Depends(json_object),
) -> dict[str, str]:
    """Reset the share link: the old token stops working for everyone at once.

    Room access and the list's room are checked in the same write transaction
    as the reset. Not an op: the answer holds the new token,
    which must not be stored for replays, and a second reset does no harm.
    """
    parse_body(ResetBody, body)
    with room_access(request, slug, write=True) as room:
        token = rotate_share_token_locked(_room_list_id(room.room_id, list_uid))
    # Open share streams find the old token gone and send `revoked`.
    notify_room_changed(room.room_id)
    return {"token": token}
