from nicegui import Client, ui
from nicegui.page import page

from ui.install_help import install_help_menu_item, open_install_help


def test_install_help_shows_steps_and_close_button():
    with Client(page("/")) as client:
        open_install_help()
        elements = list(client.elements.values())
        dialog = next(element for element in elements if isinstance(element, ui.dialog))
        instructions = next(
            element for element in elements if isinstance(element, ui.markdown)
        ).content
        assert dialog.value is True
        for text in (
            "Safari recommended",
            "Chrome recommended",
            "**Share**",
            "**Add to Home Screen**",
            "**Open as Web App**",
            "**Install app**",
            "Using another browser?",
            "last-used room",
            "sign in again",
        ):
            assert text in instructions
        close = next(
            element
            for element in elements
            if isinstance(element, ui.button) and element.text == "Close"
        )
        next(iter(close._event_listeners.values())).handler(None)
        assert dialog.value is False


def test_install_help_menu_opens_dialog():
    with Client(page("/")) as client:
        with ui.menu():
            install_help_menu_item()
        item = next(
            element
            for element in client.elements.values()
            if isinstance(element, ui.menu_item)
        )
        assert "Add to Home Screen" in str(item)
        next(iter(item._event_listeners.values())).handler(None)
        assert any(
            isinstance(element, ui.dialog) and element.value
            for element in client.elements.values()
        )
