"""Retry-safe writes: one stored response per `op_id` (docs/api.md, "Writing").

The lookup, the write and the stored response share the caller's write
transaction, so a retry either sees the whole result or nothing. Applied and
rejected responses are stored; HTTP errors are raised and nothing is stored.
Old entries are pruned at startup (`database_crud.prune_processed_ops`).
"""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from api.errors import ApiError
from database_crud import find_processed_op_locked, store_processed_op_locked

Response = dict[str, Any]


def request_hash(body: BaseModel) -> str:
    """sha256 of the validated body as canonical JSON."""
    canonical = json.dumps(
        body.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_once_locked(
    room_id: int, op_id: str, body_hash: str, run: Callable[[], Response]
) -> tuple[Response, bool]:
    """Replay the stored response for `op_id`, or run the op and store it.

    Call inside room_access(write=True). Returns (response, replayed). The
    same `op_id` with another body, or for another room, is 409
    `op_id_reused`.
    """
    stored = find_processed_op_locked(op_id)
    if stored is not None:
        stored_room_id, stored_hash, response_json = stored
        if stored_room_id != room_id or stored_hash != body_hash:
            raise ApiError(409, "op_id_reused")
        return json.loads(response_json), True
    response = run()
    store_processed_op_locked(op_id, room_id, body_hash, json.dumps(response))
    return response, False
