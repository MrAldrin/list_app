"""Live updates: a Server-Sent Events stream per room (docs/api.md).

`GET /api/v1/rooms/{slug}/events` only says "the room seq is now N"; the
client then reads the changes feed. The stream wakes up when a write may have
changed the room (see `live_updates`) and for a keep-alive. On every wake it
checks access and reads the seq in one short transaction, in a worker thread
so the event loop is not blocked. It sends `seq` only when the seq changed,
so extra wakes are harmless.

The stream never ends by itself. On shutdown, uvicorn waits up to
`timeout_graceful_shutdown` seconds (set in `main.py`) for open responses,
then cancels them, which closes the stream.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

import live_updates
from api.access import room_token, share_access, token_access
from api.errors import ApiError
from database_crud import get_room_seq_locked

# Seconds between keep-alive comments. Tests set it lower.
KEEPALIVE_SECONDS = 15.0

KEEPALIVE = ": keep-alive\n\n"

router = APIRouter()


def _room_seq(slug: str, token: str | None) -> tuple[int, int]:
    """(room_id, seq) after an access check; raises ApiError without access."""
    with token_access(slug, token) as room:
        return room.room_id, get_room_seq_locked(room.room_id)


def _share_seq(token: str) -> tuple[int, int]:
    """(room_id, seq) of a shared list's room; raises ApiError when reset."""
    with share_access(token) as share:
        return share.room_id, get_room_seq_locked(share.room_id)


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


async def _stream(
    read: Callable[[], tuple[int, int]], room_id: int
) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    # Subscribe before the first read, so no write is missed in between.
    with live_updates.subscribe(room_id) as subscription:
        last_seq: int | None = None
        next_keepalive = loop.time() + KEEPALIVE_SECONDS
        while True:
            try:
                _, seq = await run_in_threadpool(read)
            except ApiError as error:
                if error.status == 401:
                    yield _event("revoked", {})
                # 503: close; the client reconnects and reads the feed.
                return
            # Any message counts as a keep-alive.
            if seq != last_seq:
                last_seq = seq
                yield _event("seq", {"seq": seq})
                next_keepalive = loop.time() + KEEPALIVE_SECONDS
            elif loop.time() >= next_keepalive:
                yield KEEPALIVE
                next_keepalive = loop.time() + KEEPALIVE_SECONDS
            # Wait for a wake or the keep-alive.
            remaining = next_keepalive - loop.time()
            if remaining > 0:
                await subscription.wait(remaining)


@router.get("/rooms/{slug}/events")
async def events(slug: str, request: Request) -> StreamingResponse:
    token = room_token(request, slug)
    # Without access, answer with the JSON error instead of a stream.
    room_id, _ = await run_in_threadpool(_room_seq, slug, token)
    return _event_stream(lambda: _room_seq(slug, token), room_id)


@router.get("/share/{token}/events")
async def share_events(token: str) -> StreamingResponse:
    """The same stream for a share link: `revoked` once the link is reset.

    It sends the seq of the list's room, the same number as the share feed
    and op answers.
    """
    room_id, _ = await run_in_threadpool(_share_seq, token)
    return _event_stream(lambda: _share_seq(token), room_id)


def _event_stream(
    read: Callable[[], tuple[int, int]], room_id: int
) -> StreamingResponse:
    return StreamingResponse(
        _stream(read, room_id),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
