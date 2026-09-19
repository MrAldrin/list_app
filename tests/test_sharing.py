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
        if isinstance(e, ui.button) and e.text == text
    )
    return next(iter(button._event_listeners.values())).handler


@pytest.mark.parametrize("kind", ["room", "list"])
@pytest.mark.parametrize(
    "result", ["shared", "cancelled", "fallback", None, TimeoutError()]
)
def test_sharing_and_copy_fallback(monkeypatch, kind, result):
    url = f"https://example.com/{kind}/abc"
    javascript = AsyncMock(side_effect=[url, result])
    monkeypatch.setattr(ui, "run_javascript", javascript)
    clipboard = Mock()
    monkeypatch.setattr(ui.clipboard, "write", clipboard)
    with Client(page("/")) as client:
        share_button(f"/{kind}/abc", kind=kind)
        asyncio.run(click(client, "Share"))
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
def test_list_header_has_share_and_options_without_install_menu(authorized):
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
        )
        buttons = [e.text for e in client.elements.values() if isinstance(e, ui.button)]
        assert "Share" in buttons
        assert "Options" in buttons
        assert not any(isinstance(e, ui.menu) for e in client.elements.values())
