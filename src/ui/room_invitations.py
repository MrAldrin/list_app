"""Small invitation views; room access continues to use the existing flow."""

import time
from collections.abc import Callable
from datetime import UTC, datetime

from nicegui import ui

from room_invitations import (
    InvitationUnavailable,
    create_invitation,
    create_room_from_invitation,
    get_invitations,
    invitation_is_active,
    revoke_invitation,
)


def _utc(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d %H:%M UTC")


def invitation_controls(is_admin: Callable[[], bool], base_url: str) -> None:
    def authorized() -> bool:
        if is_admin():
            return True
        ui.notify("Admin sign-in required", color="negative")
        return False

    if not authorized():
        return

    ui.separator()
    ui.label("Room invitations").classes("text-lg font-bold")
    ui.label("Reusable for 7 days. Anyone with the link can create a room.").classes(
        "text-sm text-gray-600"
    )

    def invitation_list() -> None:
        if not is_admin():
            return
        for invitation in get_invitations():
            invitation_id = invitation["id"]
            active = (
                invitation["revoked_at"] is None
                and invitation["expires_at"] > time.time()
            )
            status = (
                "Revoked"
                if invitation["revoked_at"] is not None
                else "Active"
                if active
                else "Expired"
            )
            with ui.column().classes("w-full gap-1"):
                ui.label(f"Invitation #{invitation_id}: {status}")
                ui.label(f"Expires {_utc(invitation['expires_at'])}").classes("text-xs")
                if active:

                    def revoke(invitation_id=invitation_id) -> None:
                        if not authorized():
                            return
                        revoke_invitation(invitation_id)
                        refresh_invitations()

                    ui.button("Revoke", on_click=revoke).props("flat color=negative")

    def generate() -> None:
        if not authorized():
            return
        invitation_id, token = create_invitation()
        url = f"{base_url.rstrip('/')}/create-room/{token}"
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-sm"):
            ui.label(f"Invitation #{invitation_id}").classes("text-lg font-bold")
            ui.label("Save this link now. It is only shown once and expires in 7 days.")
            ui.input("Invitation link", value=url).props("readonly").classes("w-full")
            ui.button("Copy link", on_click=lambda: ui.clipboard.write(url))
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()
        refresh_invitations()

    ui.button("Generate 7-day invitation", on_click=generate).classes("w-full")
    listing = ui.column().classes("w-full")

    def refresh_invitations() -> None:
        listing.clear()
        with listing:
            invitation_list()

    refresh_invitations()


def creation_form(token: str) -> None:
    with ui.card().classes("w-full max-w-sm mx-auto"):
        ui.label("Create your room").classes("text-xl font-bold")
        if not invitation_is_active(token):
            ui.label("This invitation is invalid or no longer active.")
            ui.label("Ask the app admin for a new invitation.")
            return
        ui.label("Choose a password. Anyone you share it with can manage this room.")
        ui.label("The app admin can also access your room.").classes("text-sm")
        name = ui.input("Room name").props("maxlength=100").classes("w-full")
        password = ui.input(
            "Room password", password=True, password_toggle_button=True
        ).classes("w-full")
        confirmation = ui.input("Confirm password", password=True).classes("w-full")
        ui.label(
            "Keep your password and room link. Next, sign in to your room."
        ).classes("text-sm")
        created = False

        def create() -> None:
            nonlocal created
            if created:
                return
            if password.value != confirmation.value:
                ui.notify("Passwords do not match", color="warning")
                return
            try:
                slug = create_room_from_invitation(token, name.value, password.value)
            except InvitationUnavailable as error:
                submit.disable()
                ui.notify(str(error), color="negative")
                return
            except ValueError as error:
                ui.notify(str(error), color="warning")
                return
            created = True
            submit.disable()
            password.value = ""
            confirmation.value = ""
            ui.navigate.to(f"/room/{slug}")

        submit = ui.button("Create room", on_click=create).classes("w-full")
