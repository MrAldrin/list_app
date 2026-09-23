"""Global list redraws must not be blocked by closed browser sessions."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from nicegui import core

from main import item_list, list_of_lists


class StaleContainer:
    is_deleted = False

    @property
    def client(self):
        raise RuntimeError("The client this element belongs to has been deleted.")

    def clear(self):
        raise AssertionError("A deleted client's UI must not be refreshed")


@pytest.mark.parametrize("refreshable", [item_list, list_of_lists])
def test_deleted_client_does_not_block_live_refresh(monkeypatch, refreshable):
    stale = SimpleNamespace(container=StaleContainer(), instance=None)
    live = SimpleNamespace(
        container=SimpleNamespace(is_deleted=False, client=object(), clear=Mock()),
        instance=None,
        args=(),
        kwargs={},
        run=Mock(return_value=None),
    )
    monkeypatch.setattr(refreshable, "targets", [stale, live])

    async def refresh():
        monkeypatch.setattr(core, "loop", asyncio.get_running_loop())
        await refreshable.refresh()

    asyncio.run(refresh())

    assert refreshable.targets == [live]
    live.container.clear.assert_called_once_with()
    live.run.assert_called_once_with(refreshable.func)
