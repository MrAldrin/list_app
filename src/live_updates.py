"""Tell open pages that room data changed.

Two kinds of pages listen:

- NiceGUI pages: main.py registers a listener that refreshes them.
- The API's live stream (`api/events.py`): each open stream holds a
  subscription and wakes up when its room may have changed.

Who calls what, so each side is told exactly once per write:

- API writes call `notify_room_changed(room_id)` after commit. It wakes the
  room's streams and calls the listeners (the NiceGUI refresh).
- NiceGUI writes call main.py's `broadcast_updates()`. It refreshes NiceGUI
  pages itself and calls `wake_streams()`, never `notify_room_changed()`, so
  the NiceGUI listener is not called again.

This module imports nothing from the app, so any module can use it without a
circular import. Wakes may come from any thread.
"""

import asyncio
import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress

logger = logging.getLogger(__name__)

Listener = Callable[[int], None]

_listeners: list[Listener] = []


def register_listener(listener: Listener) -> None:
    """Call `listener(room_id)` after each change. Registering twice is a no-op."""
    if listener not in _listeners:
        _listeners.append(listener)


def notify_room_changed(room_id: int) -> None:
    """Wake the room's streams and call every listener.

    Call after commit, never while holding the DB lock. The write is already
    saved, so a failing listener is logged, not raised.
    """
    wake_streams(room_id)
    for listener in list(_listeners):
        try:
            listener(room_id)
        except Exception:
            logger.exception("Live-update listener failed")


class Subscription:
    """One open stream's wake-up signal. Create it with `subscribe()`."""

    def __init__(self, room_id: int) -> None:
        self.room_id = room_id
        self._loop = asyncio.get_running_loop()
        self._event = asyncio.Event()

    def _wake(self) -> None:
        # Called from any thread; asyncio.Event belongs to its loop.
        # A closed loop raises RuntimeError: its stream is gone anyway.
        with suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._event.set)

    async def wait(self, timeout: float) -> bool:
        """Wait up to `timeout` seconds; True if the room may have changed.

        A wake can be spurious (another room, or no change), so the stream
        reads the room seq again and sends only real changes.
        """
        try:
            await asyncio.wait_for(self._event.wait(), timeout)
        except TimeoutError:
            return False
        self._event.clear()
        return True


_subscriptions: set[Subscription] = set()
_subscriptions_lock = threading.Lock()


@contextmanager
def subscribe(room_id: int) -> Iterator[Subscription]:
    """Hold a subscription for one stream; call inside the stream's loop."""
    subscription = Subscription(room_id)
    with _subscriptions_lock:
        _subscriptions.add(subscription)
    try:
        yield subscription
    finally:
        with _subscriptions_lock:
            _subscriptions.discard(subscription)


def wake_streams(room_id: int | None = None) -> None:
    """Wake the streams of one room, or of every room when `room_id` is None.

    NiceGUI writes do not know the room, so they wake every stream; each
    stream checks its own room's seq.
    """
    with _subscriptions_lock:
        targets = [
            subscription
            for subscription in _subscriptions
            if room_id is None or subscription.room_id == room_id
        ]
    for subscription in targets:
        subscription._wake()
