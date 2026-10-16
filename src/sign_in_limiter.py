"""A short in-memory limit on sign-in attempts. One process only.

Each attempt takes one slot in every bucket it uses (for example one per room
and one per client address). A failed attempt keeps its slots; a successful
attempt gives them back, so only failures count. When a bucket is full, the
attempt is refused with the seconds to wait, before any password is checked.

Memory is bounded: a bucket holds at most its limit of timestamps, and the
number of buckets is capped (the oldest are dropped first). State is lost on
restart, which is acceptable for a limit of one minute.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable, Hashable, Sequence
from contextlib import suppress
from dataclasses import dataclass

WINDOW_SECONDS = 60.0
ROOM_LIMIT = 10  # Failed attempts per room in the window.
CLIENT_LIMIT = 20  # Failed attempts per client address in the window.
ADMIN_LIMIT = 10  # Failed admin sign-ins in the window, for all clients.
MAX_BUCKETS = 10_000


@dataclass(frozen=True)
class Reservation:
    """The slots taken by one attempt, to give back on success."""

    keys: tuple[Hashable, ...]
    stamp: float


class SignInLimiter:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        window: float = WINDOW_SECONDS,
        max_buckets: int = MAX_BUCKETS,
    ) -> None:
        self._clock = clock
        self._window = window
        self._max_buckets = max_buckets
        self._buckets: dict[Hashable, deque[float]] = {}
        self._lock = threading.Lock()

    def reserve(self, limits: Sequence[tuple[Hashable, int]]) -> Reservation | int:
        """Take one slot in each (bucket, limit), or refuse.

        Returns a Reservation, or the whole seconds (at least 1) to wait when
        any bucket is full. A refused attempt takes no slot.
        """
        with self._lock:
            now = self._clock()
            waits: list[float] = []
            for key, limit in limits:
                stamps = self._live(key, now)
                if stamps is not None and len(stamps) >= limit:
                    # The attempt may go once enough of the oldest stamps expire.
                    waits.append(stamps[len(stamps) - limit] + self._window - now)
            if waits:
                return max(1, math.ceil(max(waits)))
            for key, _limit in limits:
                self._buckets.setdefault(key, deque()).append(now)
            self._trim(now)
            return Reservation(tuple(key for key, _limit in limits), now)

    def release(self, reservation: Reservation) -> None:
        """A successful attempt: give its slots back."""
        with self._lock:
            for key in reservation.keys:
                stamps = self._buckets.get(key)
                if stamps is None:
                    continue
                with suppress(ValueError):  # Already expired.
                    stamps.remove(reservation.stamp)
                if not stamps:
                    del self._buckets[key]

    def reset(self) -> None:
        """Forget every attempt (tests)."""
        with self._lock:
            self._buckets.clear()

    def _live(self, key: Hashable, now: float) -> deque[float] | None:
        """The bucket's timestamps inside the window; drops it when empty."""
        stamps = self._buckets.get(key)
        if stamps is None:
            return None
        while stamps and stamps[0] <= now - self._window:
            stamps.popleft()
        if not stamps:
            del self._buckets[key]
            return None
        return stamps

    def _trim(self, now: float) -> None:
        if len(self._buckets) <= self._max_buckets:
            return
        for key in list(self._buckets):
            self._live(key, now)
        while len(self._buckets) > self._max_buckets:
            del self._buckets[next(iter(self._buckets))]
