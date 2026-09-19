"""Shared, browser-independent home-screen installation help."""

from nicegui import ui


def open_install_help() -> None:
    """Show manual steps without changing installation or room routing."""
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
        ui.label("Add ListR to your home screen").classes("text-lg font-bold")
        ui.label("Open ListR from your home screen, like an app.")
        ui.label("Open your room and sign in first.")
        ui.markdown(
            """
### iPhone/iPad — Safari recommended
1. Tap **Share** (you may find it inside the menu).
2. Choose **Add to Home Screen**.
3. Enable **Open as Web App**, if shown.
4. Tap **Add**.

### Android — Chrome recommended
1. Open the **⋮ menu**.
2. Tap **Add to Home screen** or **Install app**.
3. Follow the prompts to confirm.

### Using another browser?
You can also use ListR in other modern browsers. Installation options and
button names may differ. If you can't find the option, try Safari on
iPhone/iPad or Chrome on Android.

Your home-screen app opens your last-used room, not necessarily the list
you're viewing. You may need to sign in again the first time. Keep your
room link handy.
"""
        ).classes("w-full")
        with ui.row().classes("w-full justify-end"):
            ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def install_help_menu_item() -> None:
    ui.menu_item("Add to Home Screen", on_click=open_install_help)
