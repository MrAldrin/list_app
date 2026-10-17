"""Tell open live streams that room data changed.

The API's live stream (`api/events.py`): opening requests reserve capacity
while checking access, and each open stream holds a subscription that wakes up
when its room may have changed.

- API writes call `notify_room_changed(room_id)` after commit. It wakes the
  room's streams and calls the registered listeners (none in production;
  tests use them to see that a write was announced).
- Writes that change a room's state outside the ops endpoint (password
  changes) call `wake_streams(room_id)` directly.

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


class Reservation:
    """One capacity slot held while a stream's access is being checked."""

    def __init__(self) -> None:
        self._reserved = True

    def release(self) -> None:
        """Return this slot unless it has already become a subscription."""
        with _subscriptions_lock:
            if self._reserved:
                _reservations.discard(self)
                self._reserved = False


_reservations: set[Reservation] = set()

# Most open streams at once. About 4 users need a handful; the cap only stops
# a runaway client from growing the set without limit.
MAX_SUBSCRIPTIONS = 100


def reserve() -> Reservation | None:
    """Atomically reserve a slot, or return None when every slot is in use."""
    with _subscriptions_lock:
        if len(_subscriptions) + len(_reservations) >= MAX_SUBSCRIPTIONS:
            return None
        reservation = Reservation()
        _reservations.add(reservation)
        return reservation


@contextmanager
def subscribe(room_id: int, reservation: Reservation) -> Iterator[Subscription]:
    """Turn a reserved slot into a subscription for one stream."""
    subscription = Subscription(room_id)
    with _subscriptions_lock:
        if reservation not in _reservations:
            raise RuntimeError("stream capacity reservation is no longer active")
        _reservations.remove(reservation)
        reservation._reserved = False
        _subscriptions.add(subscription)
    try:
        yield subscription
    finally:
        with _subscriptions_lock:
            _subscriptions.discard(subscription)


def wake_streams(room_id: int | None = None) -> None:
    """Wake the streams of one room, or of every room when `room_id` is None.

    Without a room, every stream wakes; each stream checks its own room's seq.
    """
    with _subscriptions_lock:
        targets = [
            subscription
            for subscription in _subscriptions
            if room_id is None or subscription.room_id == room_id
        ]
    for subscription in targets:
        subscription._wake()
