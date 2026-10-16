"""Live updates: a Server-Sent Events stream per room (docs/api.md).

`GET /api/v1/rooms/{slug}/events` only says "the room seq is now N"; the
client then reads the changes feed. The stream wakes up when a write may have
changed the room (see `live_updates`) and at least every `RECHECK_SECONDS`.
On every wake it checks access and reads the seq in one short transaction, in
a worker thread so the event loop is not blocked. It sends `seq` only when the
seq changed, so extra wakes are harmless.

FastAPI's `EventSourceResponse` does the SSE encoding and the keep-alive
comments. A dependency checks access before the stream starts, so a refused
connection gets the JSON error instead of a stream.

The stream never ends by itself. On shutdown, uvicorn waits up to
`timeout_graceful_shutdown` seconds (set in `main.py`) for open responses,
then cancels them, which closes the stream.
"""

from collections.abc import AsyncGenerator, AsyncIterable, Callable
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette.concurrency import run_in_threadpool

import live_updates
from api.access import room_token, share_access, token_access
from api.errors import ApiError
from database_crud import get_room_seq_locked

# Seconds between access and seq checks when no write wakes the stream. A
# password change or a reset link is noticed within this time. Tests set it lower.
RECHECK_SECONDS = 15.0

router = APIRouter()


def _room_seq(slug: str, token: str | None) -> tuple[int, int]:
    """(room_id, seq) after an access check; raises ApiError without access."""
    with token_access(slug, token) as room:
        return room.room_id, get_room_seq_locked(room.room_id)


def _share_seq(token: str) -> tuple[int, int]:
    """(room_id, seq) of a shared list's room; raises ApiError when reset."""
    with share_access(token) as share:
        return share.room_id, get_room_seq_locked(share.room_id)


async def _room_stream_access(slug: str, request: Request) -> int:
    """Check room access before the stream starts; returns the room id."""
    room_id, _ = await run_in_threadpool(_room_seq, slug, room_token(request, slug))
    return room_id


async def _share_stream_access(token: str) -> int:
    """Check the share link before the stream starts; returns the room id."""
    room_id, _ = await run_in_threadpool(_share_seq, token)
    return room_id


async def _stream(
    room_id: int, read: Callable[[], tuple[int, int]]
) -> AsyncGenerator[ServerSentEvent]:
    # Subscribe before the first read, so no write is missed in between.
    with live_updates.subscribe(room_id) as subscription:
        last_seq: int | None = None
        while True:
            try:
                _, seq = await run_in_threadpool(read)
            except ApiError as error:
                if error.status == 401:
                    yield ServerSentEvent(event="revoked", data={})
                # 503: close; the client reconnects and reads the feed.
                return
            if seq != last_seq:
                last_seq = seq
                yield ServerSentEvent(event="seq", data={"seq": seq})
            await subscription.wait(RECHECK_SECONDS)


@router.get("/rooms/{slug}/events", response_class=EventSourceResponse)
async def events(
    slug: str,
    request: Request,
    room_id: Annotated[int, Depends(_room_stream_access)],
) -> AsyncIterable[ServerSentEvent]:
    token = room_token(request, slug)
    async with aclosing(_stream(room_id, lambda: _room_seq(slug, token))) as stream:
        async for event in stream:
            yield event


@router.get("/share/{token}/events", response_class=EventSourceResponse)
async def share_events(
    token: str,
    room_id: Annotated[int, Depends(_share_stream_access)],
) -> AsyncIterable[ServerSentEvent]:
    """The same stream for a share link: `revoked` once the link is reset.

    It sends the seq of the list's room, the same number as the share feed
    and op answers.
    """
    async with aclosing(_stream(room_id, lambda: _share_seq(token))) as stream:
        async for event in stream:
            yield event
