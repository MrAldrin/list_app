import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from nicegui import Client, ui
from nicegui.elements.number import Number
from nicegui.elements.switch import Switch
from nicegui.functions.refreshable import refreshable
from nicegui.page import page

import main
from database_crud import (
    add_list_tag,
    create_list,
    get_list_data,
    get_list_details,
    update_list_visibility_settings,
)
from database_setup import db
from item_visibility import MAX_HIDE_DONE_COUNT


def make_state(*, edit_mode=True):
    return {
        "filter_tag": None,
        "edit_mode": edit_mode,
        "pending_undo": None,
        "focus_tag_input": False,
        "show_counters": False,
        "only_gt_1": False,
    }


def make_list(name="visibility"):
    room_id = db.execute("SELECT id FROM rooms LIMIT 1").fetchone()[0]
    return create_list(name, room_id)


def render_tags(client, list_id, slug, state):
    tags_ui = main._create_tags_ui(
        list_id,
        slug,
        state,
        Mock(),
        lambda: True,
        Mock(),
    )
    tags_ui()


def settings_switch(client, label):
    return next(
        element
        for element in client.elements.values()
        if isinstance(element, Switch) and element.text == label
    )


def change_switch(switch, value):
    switch._change_handlers[-1](SimpleNamespace(value=value))


def number_input(client, label):
    return next(
        element
        for element in client.elements.values()
        if isinstance(element, Number) and element.label == label
    )


def blur(number):
    listeners = [
        listener
        for listener in number._event_listeners.values()
        if listener.type == "blur"
    ]
    listeners[-1].handler()


def prepare_ui_callbacks(monkeypatch):
    monkeypatch.setattr(refreshable, "refresh", Mock(return_value=None))
    monkeypatch.setattr(main, "broadcast_updates", Mock())
    monkeypatch.setattr(main.ui, "notify", Mock())


def test_options_show_main_switch_off_by_default(monkeypatch):
    prepare_ui_callbacks(monkeypatch)
    list_id, slug = make_list()

    with Client(page("/")) as client:
        render_tags(client, list_id, slug, make_state())

        assert settings_switch(client, "Hide checked-off items").value is False
        assert not any(
            isinstance(element, Switch)
            and element.text in {"Only after X days", "Keep last X checked items"}
            for element in client.elements.values()
        )
        assert get_list_details(list_id)["hide_done_mode"] == "off"


def test_main_switch_reenables_all_and_settings_updates_merge(
    monkeypatch,
):
    prepare_ui_callbacks(monkeypatch)
    list_id, slug = make_list()
    update_list_visibility_settings(
        list_id, mode="age", age_days=7, recent_count=3, expected_slug=slug
    )

    with Client(page("/")) as client:
        state = make_state()
        render_tags(client, list_id, slug, state)
        main_switch = settings_switch(client, "Hide checked-off items")
        assert main_switch.value is True

        change_switch(main_switch, False)
        assert get_list_details(list_id)["hide_done_mode"] == "off"
        change_switch(main_switch, True)
        restored = get_list_details(list_id)
        assert restored["hide_done_mode"] == "all"
        assert restored["hide_done_age_days"] == 7
        assert restored["hide_done_recent_count"] == 3

        # A stale switch and counter callback reload persisted fields and change
        # only their own setting after another viewer selects recent mode.
        update_list_visibility_settings(
            list_id, mode="recent", age_days=7, recent_count=12, expected_slug=slug
        )
        age_input = number_input(client, "Days before hiding")
        change_switch(settings_switch(client, "Keep last X checked items"), True)
        age_input.value = 0
        blur(age_input)
        merged = get_list_details(list_id)
        assert merged["hide_done_mode"] == "recent"
        assert merged["hide_done_age_days"] == 0
        assert merged["hide_done_recent_count"] == 12


def test_submodes_are_exclusive_and_counter_validation_allows_zero(monkeypatch):
    prepare_ui_callbacks(monkeypatch)
    list_id, slug = make_list()
    update_list_visibility_settings(
        list_id, mode="all", age_days=7, recent_count=10, expected_slug=slug
    )

    with Client(page("/")) as client:
        state = make_state()
        render_tags(client, list_id, slug, state)
        change_switch(settings_switch(client, "Only after X days"), True)
        assert get_list_details(list_id)["hide_done_mode"] == "age"
        main.visibility_settings_ui(list_id, slug, state, lambda: True, Mock())

        age_input = number_input(client, "Days before hiding")
        age_input.value = 0
        blur(age_input)
        assert get_list_details(list_id)["hide_done_age_days"] == 0

        # Select recent with the already-rendered mutually exclusive switch.
        change_switch(settings_switch(client, "Keep last X checked items"), True)
        assert get_list_details(list_id)["hide_done_mode"] == "recent"

        # Render the recent counter and check both the lower and upper bounds.
        main.visibility_settings_ui(list_id, slug, make_state(), lambda: True, Mock())
        recent_input = number_input(client, "Checked items to keep")
        recent_input.value = 0
        blur(recent_input)
        assert get_list_details(list_id)["hide_done_recent_count"] == 0

        recent_input.value = MAX_HIDE_DONE_COUNT
        blur(recent_input)
        assert (
            get_list_details(list_id)["hide_done_recent_count"] == MAX_HIDE_DONE_COUNT
        )

        recent_input.value = 1.5
        blur(recent_input)
        assert (
            get_list_details(list_id)["hide_done_recent_count"] == MAX_HIDE_DONE_COUNT
        )
        recent_input.value = -1
        blur(recent_input)
        assert (
            get_list_details(list_id)["hide_done_recent_count"] == MAX_HIDE_DONE_COUNT
        )
        main.ui.notify.assert_called()


def test_visibility_delete_undo_payload_keeps_completion_time(monkeypatch):
    prepare_ui_callbacks(monkeypatch)
    list_id, slug = make_list()
    set_pending_undo = Mock()
    monkeypatch.setattr(main, "delete_item_from_list", Mock())
    item = {
        "id": 19,
        "name": "milk",
        "done": True,
        "active_tags": ["cold"],
        "description": "whole",
        "quantity": 2,
        "completed_at": "2026-01-02T03:04:05.000000Z",
    }

    main._delete_item_with_undo(
        list_id,
        slug,
        item,
        set_pending_undo,
        lambda: True,
        Mock(),
    )

    assert (
        set_pending_undo.call_args.args[0]["payload"]["completed_at"]
        == item["completed_at"]
    )


def test_stale_visibility_callback_rejects_a_deleted_list(monkeypatch):
    prepare_ui_callbacks(monkeypatch)
    list_id, slug = make_list("deleted settings target")
    unavailable = Mock()

    with Client(page("/")) as client:
        main.visibility_settings_ui(
            list_id, slug, make_state(), lambda: True, unavailable
        )
        main_switch = settings_switch(client, "Hide checked-off items")
        db.execute("DELETE FROM lists WHERE id = ?", (list_id,))
        db.commit()
        replacement_id, _replacement_slug = make_list("replacement list")

        change_switch(main_switch, True)

        assert unavailable.call_count == 1
        assert get_list_details(replacement_id)["hide_done_mode"] == "off"


def test_item_rows_apply_visibility_before_tag_filter_without_changing_history(
    monkeypatch,
):
    prepare_ui_callbacks(monkeypatch)
    list_id, slug = make_list()
    add_list_tag(list_id, "produce", expected_slug=slug)
    db.executemany(
        """
        INSERT INTO items (name, done, list_id, active_tags, completed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            ("open produce", 0, list_id, '["produce"]', None),
            (
                "older checked produce",
                1,
                list_id,
                '["produce"]',
                "2026-01-01T00:00:00Z",
            ),
            ("newer checked dairy", 1, list_id, "[]", "2026-01-02T00:00:00Z"),
        ],
    )
    db.commit()
    update_list_visibility_settings(
        list_id, mode="recent", age_days=7, recent_count=1, expected_slug=slug
    )

    with Client(page("/")) as client:
        main.item_list(list_id, lambda: "produce", list_slug=slug)
        labels = [
            element.text
            for element in client.elements.values()
            if isinstance(element, ui.label)
        ]
        assert "open produce" in labels
        assert "older checked produce" not in labels
        assert "newer checked dairy" not in labels

    _items, history = get_list_data(list_id)
    assert history == ["newer checked dairy", "older checked produce", "open produce"]


def test_age_timer_refreshes_only_its_page_but_broadcast_still_refreshes_all(
    monkeypatch,
):
    first_id, _ = make_list("first age list")
    second_id, _ = make_list("second age list")
    first = get_list_details(first_id)
    second = get_list_details(second_id)
    for details in (first, second):
        update_list_visibility_settings(
            details["id"],
            mode="age",
            age_days=7,
            recent_count=10,
            expected_slug=f"share:{details['share_token']}",
        )

    monkeypatch.setattr(main, "app", SimpleNamespace(storage=SimpleNamespace(user={})))
    monkeypatch.setattr(main, "_cleanup_legacy_room_password_keys", AsyncMock())
    monkeypatch.setattr(
        main, "_get_browser_storage", AsyncMock(return_value=(True, None))
    )
    timers = []

    def timer(interval, callback, **kwargs):
        if interval == 60.0:
            timers.append(callback)
        return SimpleNamespace(cancel=Mock())

    monkeypatch.setattr(main.ui, "timer", timer)
    original_get_list_data = main.get_list_data
    reads = []

    def read_list(list_id):
        reads.append(list_id)
        return original_get_list_data(list_id)

    monkeypatch.setattr(main, "get_list_data", read_list)

    async def render_and_refresh():
        monkeypatch.setattr(main.core, "loop", asyncio.get_running_loop())
        with Client(page("/")):
            await main.shared_list_page(first["share_token"])
            with Client(page("/")):
                await main.shared_list_page(second["share_token"])
                assert len(timers) == 2
                reads.clear()
                timers[0]()
                await asyncio.sleep(0)
                assert reads == [first_id]
                reads.clear()
                main.broadcast_updates(refresh_lists=False)
                await asyncio.sleep(0)
                assert sorted(reads) == sorted([first_id, second_id])

    asyncio.run(render_and_refresh())
