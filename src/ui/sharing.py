"""Public URL sharing, without query parameters or browser credentials."""

import json

from nicegui import ui


def share_button(path: str, *, kind: str, as_menu_item: bool = False) -> None:
    """Render a sharing button or menu item with the same copy-dialog fallback."""
    message = (
        "The recipient will also need the room password."
        if kind == "room"
        else "Anyone with this link can open this list."
    )
    # Use the supplied resource path, not location.href (which may contain
    # admin flags or other query parameters). Never read browser access tokens.
    url_expression = f"new URL({json.dumps(path)}, window.location.origin).href"

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
        ui.label(f"Share this {kind}").classes("text-lg font-bold")
        ui.label(message).classes("text-sm text-gray-600 mb-2")
        url_input = ui.input(value=path).props("readonly").classes("w-full")

        async def copy_link() -> None:
            ui.clipboard.write(url_input.value)
            ui.notify("Link copied", color="positive", position="top")

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Close", on_click=dialog.close).props("flat")
            ui.button("Copy link", on_click=copy_link)

    async def share() -> None:
        # Resolve the canonical URL first so even a native-sharing failure can
        # fall back to an absolute link suitable for sending to another device.
        try:
            url = await ui.run_javascript(f"return {url_expression}", timeout=3.0)
        except TimeoutError:
            ui.notify("Could not prepare the link. Please retry.", color="warning")
            return
        if not isinstance(url, str) or not url:
            ui.notify("Could not prepare the link. Please retry.", color="warning")
            return
        url_input.value = url
        try:
            result = await ui.run_javascript(
                f"""
                if (navigator.share) {{
                    try {{
                        await navigator.share({{
                            title: 'ListR',
                            text: {json.dumps(message)},
                            url: {json.dumps(url)},
                        }});
                        return 'shared';
                    }} catch (error) {{
                        if (error && error.name === 'AbortError') return 'cancelled';
                    }}
                }}
                return 'fallback';
                """,
                timeout=10.0,
            )
        except TimeoutError:
            result = "fallback"
        if result not in ("shared", "cancelled"):
            dialog.open()

    if as_menu_item:
        ui.menu_item(f"Share {kind.title()}", on_click=share)
    else:
        ui.button("Share", on_click=share).props("flat")
