"""The JSON API for the Svelte frontend, under /api/v1.

The contract is in docs/api.md. Register it with `register_api(app)`.
"""

from fastapi import APIRouter, Depends, FastAPI

from api import session
from api.errors import install_error_handlers
from api.requests import NoStoreMiddleware, check_write_request

API_V1 = "/api/v1"


def build_router() -> APIRouter:
    """The /api/v1 router. Every route gets the same-origin write check."""
    router = APIRouter(prefix=API_V1, dependencies=[Depends(check_write_request)])
    router.include_router(session.router)
    return router


def register_api(app: FastAPI) -> None:
    """Add the API routes, JSON errors and no-store headers to the app."""
    app.include_router(build_router())
    install_error_handlers(app)
    app.add_middleware(NoStoreMiddleware)
