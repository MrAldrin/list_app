"""Tell open pages that room data changed.

API writes call `notify_room_changed(room_id)` after their transaction
commits. Listeners register at startup: main.py adds NiceGUI's page refresh.
This module imports nothing from the app, so any module can use it without a
circular import.
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

Listener = Callable[[int], None]

_listeners: list[Listener] = []


def register_listener(listener: Listener) -> None:
    """Call `listener(room_id)` after each change. Registering twice is a no-op."""
    if listener not in _listeners:
        _listeners.append(listener)


def notify_room_changed(room_id: int) -> None:
    """Call every listener. Call after commit, never while holding the DB lock.

    The write is already saved, so a failing listener is logged, not raised.
    """
    for listener in list(_listeners):
        try:
            listener(room_id)
        except Exception:
            logger.exception("Live-update listener failed")
