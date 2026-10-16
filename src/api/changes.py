"""The changes feed: the one read path for room data (docs/api.md).

`GET /api/v1/rooms/{slug}/changes?since=N` returns the lists, items and
deletions changed after room seq N, read in one transaction with the access
check, so `seq` and the rows always match.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from api.access import room_access
from database_crud import (
    get_deletions_locked,
    get_deletions_pruned_seq_locked,
    get_item_changes_locked,
    get_list_changes_locked,
    get_room_details_locked,
    get_room_seq_locked,
)

# SQLite integers are 64-bit; a larger `since` is a bad request, not a crash.
MAX_SEQ = 2**63 - 1

router = APIRouter()


@router.get("/rooms/{slug}/changes")
def changes(
    slug: str,
    request: Request,
    since: Annotated[int, Query(ge=0, le=MAX_SEQ)],
) -> dict[str, Any]:
    with room_access(request, slug) as room:
        seq = get_room_seq_locked(room.room_id)
        pruned_seq = get_deletions_pruned_seq_locked(room.room_id)
        # A full snapshot on first load, when the client is ahead of the server
        # (for example after a database restore), and when the client is behind
        # pruned deletion records: it may have missed some of them.
        full = since == 0 or since > seq or since < pruned_seq
        rows_since = None if full else since
        return {
            "seq": seq,
            "full": full,
            "room": get_room_details_locked(room.room_id),
            "lists": get_list_changes_locked(room.room_id, rows_since),
            "items": get_item_changes_locked(room.room_id, rows_since),
            "deletions": [] if full else get_deletions_locked(room.room_id, since),
        }
