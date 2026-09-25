import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from nicegui import Client, core, ui
from nicegui.page import page

from main import _render_header
from ui.sharing import share_button


async def click(client, text):
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(core, "loop", asyncio.get_running_loop())
        handler(client, text)(None)
        await asyncio.sleep(0)
        await asyncio.sleep(0)


def handler(client, text):
    button = next(
        e
        for e in client.elements.values()
        if (isinstance(e, ui.button) and e.text == text)
        or (
            isinstance(e, ui.menu_item)
            and any(
                isinstance(child, ui.item_section) and child.text == text
                for child in e.default_slot.children
            )
        )
    )
    return next(iter(button._event_listeners.values())).handler


@pytest.mark.parametrize("kind, as_menu_item", [("room", True), ("list", False)])
@pytest.mark.parametrize(
    "result", ["shared", "cancelled", "fallback", None, TimeoutError()]
)
def test_sharing_and_copy_fallback(monkeypatch, kind, as_menu_item, result):
    url = f"https://example.com/{kind}/abc"
    javascript = AsyncMock(side_effect=[url, result])
    monkeypatch.setattr(ui, "run_javascript", javascript)
    clipboard = Mock()
    monkeypatch.setattr(ui.clipboard, "write", clipboard)
    with Client(page("/")) as client:
        if as_menu_item:
            with ui.menu() as menu:
                share_button(f"/{kind}/abc", kind=kind, as_menu_item=True)
            item = next(
                e for e in client.elements.values() if isinstance(e, ui.menu_item)
            )
            assert item.parent_slot.parent is menu
            assert not any(
                isinstance(e, ui.button) and e.text == "Share"
                for e in client.elements.values()
            )
        else:
            share_button(f"/{kind}/abc", kind=kind)
        asyncio.run(click(client, f"Share {kind.title()}" if as_menu_item else "Share"))
        dialog = next(e for e in client.elements.values() if isinstance(e, ui.dialog))
        assert bool(dialog.value) == (result not in ("shared", "cancelled"))
        scripts = [call.args[0] for call in javascript.call_args_list]
        assert f'new URL("/{kind}/abc", window.location.origin)' in scripts[0]
        assert all(
            "location.href" not in s and "localStorage" not in s for s in scripts
        )
        assert url in scripts[1]
        message = (
            "The recipient will also need the room password."
            if kind == "room"
            else "Anyone with this link can open this list."
        )
        assert message in scripts[1]
        assert any(
            isinstance(e, ui.label) and e.text == message
            for e in client.elements.values()
        )
        if dialog.value:
            asyncio.run(click(client, "Copy link"))
            clipboard.assert_called_once_with(url)
            handler(client, "Close")(None)
            assert not dialog.value


@pytest.mark.parametrize("result", [None, "", TimeoutError()])
def test_url_resolution_failure_does_not_share_relative_link(monkeypatch, result):
    javascript = AsyncMock(side_effect=[result])
    monkeypatch.setattr(ui, "run_javascript", javascript)
    notify = Mock()
    monkeypatch.setattr(ui, "notify", notify)
    with Client(page("/")) as client:
        share_button("/room/abc", kind="room")
        asyncio.run(click(client, "Share"))
        assert javascript.call_count == 1
        notify.assert_called_once()
        assert not any(
            isinstance(e, ui.dialog) and e.value for e in client.elements.values()
        )


@pytest.mark.parametrize("authorized", [True, False])
def test_list_header_keeps_options_visible_and_hides_sharing_in_menu(
    authorized, monkeypatch
):
    monkeypatch.setattr(
        "main.get_list_details_by_identity", lambda _: {"share_token": "x" * 43}
    )
    with Client(page("/")) as client:
        _render_header(
            "Shopping",
            "list-slug",
            authorized,
            {"edit_mode": False},
            Mock(),
            Mock(),
            "room-slug",
            lambda: True,
            Mock() if authorized else None,
        )
        buttons = [e.text for e in client.elements.values() if isinstance(e, ui.button)]
        menu = next(e for e in client.elements.values() if isinstance(e, ui.menu))
        items = [
            e
            for e in client.elements.values()
            if isinstance(e, ui.menu_item) and e.parent_slot.parent is menu
        ]
        labels = [
            child.text
            for item in items
            for child in item.default_slot.children
            if isinstance(child, ui.item_section)
        ]
        assert "Share" not in buttons
        assert "Reset share link" not in buttons
        assert "Options" in buttons
        assert "Share List" in labels
        assert ("Reset share link" in labels) == authorized
        assert not any("Add to Home Screen" in label for label in labels)
