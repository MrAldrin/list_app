"""The JSON error format of the API, and error handlers scoped to /api paths.

Every API error looks like {"error": {"code": ..., "message": ...}}. NiceGUI
installs its own handlers (HTML error pages); ours wrap them and only answer
for /api paths, so NiceGUI pages behave as before.
"""

import inspect
import sqlite3
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

API_PREFIX = "/api"
NO_STORE = "no-store"

MESSAGES = {
    "invalid_request": "This request is not valid.",
    "invalid_password": "Wrong room or password.",
    "not_authenticated": "Sign in to this room.",
    "share_unavailable": "This list was deleted or this share link was reset.",
    "list_unavailable": "The list is no longer available.",
    "wrong_password": "Incorrect password",
    "admin_required": "Admin sign-in required",
    "room_unavailable": "Room changed or no longer exists; refresh and try again",
    "forbidden_origin": "This request must come from this site.",
    "not_found": "Not found.",
    "op_id_reused": "This op_id was already used for another request.",
    "unavailable": "The server is busy. Please try again.",
    "internal_error": "Something went wrong on the server.",
}

Handler = Callable[[Request, Exception], Awaitable[Response] | Response]


class ApiError(Exception):
    """Raise in API code to answer with the JSON error format."""

    def __init__(self, status: int, code: str, message: str | None = None) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message or MESSAGES[code]


def is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def error_response(
    status: int,
    code: str,
    message: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message or MESSAGES[code]}},
        status_code=status,
        headers={**(headers or {}), "Cache-Control": NO_STORE},
    )


def _code_for_status(status: int) -> str:
    if status == 404:
        return "not_found"
    if status == 401:
        return "not_authenticated"
    if status >= 500:
        return "unavailable"
    return "invalid_request"


async def _call(handler: Handler, request: Request, exc: Exception) -> Response:
    result = handler(request, exc)
    return await result if inspect.isawaitable(result) else result


async def _api_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ApiError)
    return error_response(exc.status, exc.code, exc.message)


def install_error_handlers(app: FastAPI) -> None:
    """Answer API errors with JSON; leave every other path to NiceGUI/FastAPI."""
    app.add_exception_handler(ApiError, _api_error_handler)

    def wrap_http(previous: Handler | None) -> Handler:
        previous = previous or http_exception_handler

        async def handler(request: Request, exc: Exception) -> Response:
            if is_api_path(request.url.path):
                assert isinstance(exc, StarletteHTTPException)
                # Keep headers such as Allow (405), never the detail text.
                return error_response(
                    exc.status_code,
                    _code_for_status(exc.status_code),
                    headers=dict(exc.headers or {}),
                )
            return await _call(previous, request, exc)

        return handler

    # Starlette looks up HTTP errors by status code first, then by class.
    # NiceGUI registers a 404 handler; FastAPI one for HTTPException.
    app.exception_handlers[404] = wrap_http(app.exception_handlers.get(404))
    app.exception_handlers[StarletteHTTPException] = wrap_http(
        app.exception_handlers.get(StarletteHTTPException)
    )

    previous_validation = (
        app.exception_handlers.get(RequestValidationError)
        or request_validation_exception_handler
    )

    async def validation_handler(request: Request, exc: Exception) -> Response:
        if is_api_path(request.url.path):
            return error_response(422, "invalid_request")
        return await _call(previous_validation, request, exc)

    app.exception_handlers[RequestValidationError] = validation_handler

    previous_unhandled = app.exception_handlers.get(Exception)

    async def unhandled_handler(request: Request, exc: Exception) -> Response:
        if is_api_path(request.url.path):
            if isinstance(exc, sqlite3.Error):
                return error_response(503, "unavailable")
            return error_response(500, "internal_error")
        if previous_unhandled is None:
            raise exc
        return await _call(previous_unhandled, request, exc)

    # Unhandled exceptions reach this handler last (Starlette's
    # ServerErrorMiddleware), which also logs them.
    app.exception_handlers[Exception] = unhandled_handler
