from types import SimpleNamespace
from unittest.mock import Mock

from nicegui import Client, ui
from nicegui.functions.refreshable import refreshable
from nicegui.page import page

import main
from database_crud import (
    add_list_tag,
    create_list,
    get_list_details_by_slug,
)
from database_setup import db


def make_state(*, filter_tag=None):
    return {
        "filter_tag": filter_tag,
        "edit_mode": True,
        "focus_tag_input": False,
    }


def render_tags_ui(client, list_id, slug, state, set_pending_undo):
    tags_ui = main._create_tags_ui(
        list_id,
        slug,
        state,
        set_pending_undo,
        lambda: True,
        Mock(),
    )
    tags_ui()


def test_stale_list_tag_add_callbacks_merge_and_keep_input_feedback(monkeypatch):
    refresh_ui = Mock(return_value=None)
    monkeypatch.setattr(refreshable, "refresh", refresh_ui)
    monkeypatch.setattr(main, "item_list", SimpleNamespace(refresh=Mock()))
    monkeypatch.setattr(main, "broadcast_updates", Mock())
    room_id = db.execute("SELECT id FROM rooms LIMIT 1").fetchone()[0]
    list_id, slug = create_list("tagged", room_id)

    with Client(page("/")) as client:
        states = [make_state(), make_state()]
        for state in states:
            render_tags_ui(client, list_id, slug, state, Mock())
        inputs = [e for e in client.elements.values() if isinstance(e, ui.input)]
        add_buttons = [
            e
            for e in client.elements.values()
            if isinstance(e, ui.button) and e._props.get("icon") == "add"
        ]
        assert len(inputs) == len(add_buttons) == 2
        inputs[0].value = "alpha"
        inputs[1].value = "beta"

        for button in add_buttons:
            next(iter(button._event_listeners.values())).handler(None)

        assert get_list_details_by_slug(slug)["list_tags"] == ["alpha", "beta"]
        assert [field.value for field in inputs] == ["", ""]
        assert refresh_ui.call_count == 2
        assert not db.in_transaction


def test_stale_list_tag_delete_callback_keeps_intervening_add(monkeypatch):
    refresh_ui = Mock(return_value=None)
    monkeypatch.setattr(refreshable, "refresh", refresh_ui)
    monkeypatch.setattr(main, "item_list", SimpleNamespace(refresh=Mock()))
    notify = Mock()
    pending_undo = Mock()
    monkeypatch.setattr(main.ui, "notify", notify)
    monkeypatch.setattr(main, "broadcast_updates", Mock())
    room_id = db.execute("SELECT id FROM rooms LIMIT 1").fetchone()[0]
    list_id, slug = create_list("tagged", room_id)
    main.add_list_tag(list_id, "remove-me", expected_slug=slug)
    state = make_state(filter_tag="remove-me")

    with Client(page("/")) as client:
        render_tags_ui(client, list_id, slug, state, pending_undo)
        delete_button = next(
            e
            for e in client.elements.values()
            if isinstance(e, ui.button) and e._props.get("icon") == "close"
        )
        add_list_tag(list_id, "concurrent-add", expected_slug=slug)

        next(iter(delete_button._event_listeners.values())).handler(None)

        assert get_list_details_by_slug(slug)["list_tags"] == ["concurrent-add"]
        notify.assert_called_once()
        assert notify.call_args.args[0] == "Deleted tag remove-me"
        assert pending_undo.call_args.args[0] == {
            "kind": "tag",
            "message": "Deleted tag remove-me",
            "payload": {"tag": "remove-me"},
        }
        assert state["filter_tag"] is None
        assert refresh_ui.call_count == 1
        assert not db.in_transaction
