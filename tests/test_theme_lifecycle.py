import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main


@pytest.mark.parametrize("outcome", ["success", "timeout", "deleted", "cancelled"])
def test_theme_setup_respects_page_lifecycle(monkeypatch, outcome: str) -> None:
    client = SimpleNamespace(is_deleted=outcome == "deleted", request=object())
    monkeypatch.setattr(
        main,
        "ui",
        SimpleNamespace(
            context=SimpleNamespace(client=client),
            dark_mode=Mock(),
            button=Mock(),
        ),
    )

    async def javascript(*args, **kwargs):
        if outcome == "cancelled":
            raise asyncio.CancelledError
        client.is_deleted = True
        if outcome == "timeout":
            raise TimeoutError
        return "dark"

    main.ui.run_javascript = javascript

    async def render() -> None:
        await main._add_theme_toggle()
        pytest.fail("Deleted page setup must not continue")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(render())
    main.ui.dark_mode.assert_not_called()
    main.ui.button.assert_not_called()


@pytest.mark.parametrize("saved_theme", ["dark", "light", None, "timeout"])
def test_live_page_theme_setup(monkeypatch, saved_theme: str | None) -> None:
    client = SimpleNamespace(is_deleted=False, request=object())
    dark_mode = Mock()
    button = Mock()

    async def javascript(*args, **kwargs):
        if saved_theme == "timeout":
            raise TimeoutError
        return saved_theme

    monkeypatch.setattr(
        main,
        "ui",
        SimpleNamespace(
            context=SimpleNamespace(client=client),
            run_javascript=javascript,
            dark_mode=dark_mode,
            button=button,
        ),
    )
    asyncio.run(main._add_theme_toggle())
    dark_mode.assert_called_once_with(value=saved_theme == "dark")
    button.assert_called_once()
