import sqlite3
from unittest.mock import Mock

from database_crud import ListUnavailable
from main import (
    _can_return_to_room,
    _list_lookup_status,
    _transition_list_state,
    _unavailable_list_message,
    broadcast_updates,
)
from room_access import RoomAccessStatus


def _active_state():
    return {
        "status": "active",
        "list_id": 1,
        "list_slug": "groceries-abc123",
        "list_name": "groceries",
        "room_slug": "home-def456",
        "room_authorized": True,
    }


def test_unavailable_message_preserves_room_access_context():
    assert _unavailable_list_message(True) == "This list was deleted."
    assert (
        _unavailable_list_message(False)
        == "This list was deleted or you no longer have access."
    )


def test_room_button_requires_existing_room_and_valid_access():
    assert _can_return_to_room(RoomAccessStatus.VALID, room_exists=True)
    assert not _can_return_to_room(RoomAccessStatus.VALID, room_exists=False)
    assert not _can_return_to_room(RoomAccessStatus.INVALID, room_exists=True)
    assert not _can_return_to_room(RoomAccessStatus.UNAVAILABLE, room_exists=True)


def test_list_state_transitions_only_once():
    state = _active_state()

    assert _transition_list_state(state)
    assert state["status"] == "unavailable"
    assert not _transition_list_state(state)


def test_transient_list_lookup_failure_is_retryable(monkeypatch):
    monkeypatch.setattr(
        "main.get_list_details_by_slug",
        lambda _slug: (_ for _ in ()).throw(sqlite3.OperationalError("busy")),
    )
    state = _active_state()

    assert _list_lookup_status(state["list_slug"]) == "retry"
    assert state["status"] == "active"


def test_missing_list_lookup_transitions_to_unavailable(monkeypatch):
    monkeypatch.setattr("main.get_list_details_by_slug", lambda _slug: None)
    state = _active_state()

    assert _list_lookup_status(state["list_slug"]) == "missing"
    assert _transition_list_state(state)
    assert state["status"] == "unavailable"


def test_deleted_list_mutations_raise_domain_error():
    assert issubclass(ListUnavailable, LookupError)


def test_deleting_a_list_refreshes_rooms_without_refreshing_items(monkeypatch):
    refresh_lists = Mock()
    refresh_items = Mock()
    monkeypatch.setattr("main.list_of_lists.refresh", refresh_lists)
    monkeypatch.setattr("main.item_list.refresh", refresh_items)

    broadcast_updates(refresh_lists=True, refresh_items=False)

    refresh_lists.assert_called_once_with()
    refresh_items.assert_not_called()
