"""The JSON API for the Svelte frontend, under /api/v1.

The contract is in docs/api.md. Register it with `register_api(app)`.
"""

from fastapi import APIRouter, Depends, FastAPI

from api import admin, changes, events, invitations, ops, room, session, share
from api.errors import install_error_handlers
from api.requests import NoStoreMiddleware, check_write_request

API_V1 = "/api/v1"


def build_router() -> APIRouter:
    """The /api/v1 router. Every route gets the same-origin write check."""
    router = APIRouter(prefix=API_V1, dependencies=[Depends(check_write_request)])
    router.include_router(session.router)
    router.include_router(changes.router)
    router.include_router(ops.router)
    router.include_router(events.router)
    router.include_router(room.router)
    router.include_router(share.router)
    router.include_router(admin.router)
    router.include_router(invitations.admin_router)
    router.include_router(invitations.router)
    return router


def register_api(app: FastAPI) -> None:
    """Add the API routes, JSON errors and no-store headers to the app."""
    app.include_router(build_router())
    install_error_handlers(app)
    app.add_middleware(NoStoreMiddleware)
