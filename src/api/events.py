"""Live updates: a Server-Sent Events stream per room (docs/api.md).

`GET /api/v1/rooms/{slug}/events` only says "the room seq is now N"; the
client then reads the changes feed. The stream wakes up when a write may have
changed the room (see `live_updates`) and for a keep-alive. On every wake it
checks access and reads the seq in one short transaction, in a worker thread
so the event loop is not blocked. It sends `seq` only when the seq changed,
so extra wakes are harmless.
"""

import asyncio
import json
import signal
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

import live_updates
from api.access import room_token, token_access
from api.errors import ApiError
from database_crud import get_room_seq_locked

# Seconds between keep-alive comments. Tests set it lower.
KEEPALIVE_SECONDS = 15.0
# How often an idle stream checks whether the server is shutting down.
SHUTDOWN_POLL_SECONDS = 0.5

KEEPALIVE = ": keep-alive\n\n"

router = APIRouter()


def server_is_stopping() -> bool:
    """True once uvicorn was told to stop (Ctrl+C, SIGTERM, a reload).

    Uvicorn waits for open responses to finish before it shuts the app down,
    so an endless stream would block shutdown and reloads. Uvicorn installs
    its server's `handle_exit` as the signal handler; the bound method leads
    to the server and its `should_exit` flag. It works in reload mode too,
    where NiceGUI's `Server.instance` is not set in the worker process.
    """
    server = getattr(signal.getsignal(signal.SIGTERM), "__self__", None)
    return bool(getattr(server, "should_exit", False))


def _room_seq(slug: str, token: str | None) -> tuple[int, int]:
    """(room_id, seq) after an access check; raises ApiError without access."""
    with token_access(slug, token) as room:
        return room.room_id, get_room_seq_locked(room.room_id)


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


async def _stream(slug: str, token: str | None, room_id: int) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    # Subscribe before the first read, so no write is missed in between.
    with live_updates.subscribe(room_id) as subscription:
        last_seq: int | None = None
        next_keepalive = loop.time() + KEEPALIVE_SECONDS
        while True:
            try:
                _, seq = await run_in_threadpool(_room_seq, slug, token)
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
            # Wait for a wake or the keep-alive, checking for shutdown.
            while True:
                if server_is_stopping():
                    return
                remaining = next_keepalive - loop.time()
                if remaining <= 0:
                    break
                if await subscription.wait(min(remaining, SHUTDOWN_POLL_SECONDS)):
                    break


@router.get("/rooms/{slug}/events")
async def events(slug: str, request: Request) -> StreamingResponse:
    token = room_token(request, slug)
    # Without access, answer with the JSON error instead of a stream.
    room_id, _ = await run_in_threadpool(_room_seq, slug, token)
    return StreamingResponse(
        _stream(slug, token, room_id),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
