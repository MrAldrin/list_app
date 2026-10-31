"""Request rules for every API endpoint: same-origin writes and JSON bodies."""

import json
from typing import Annotated, Any

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from api.errors import NO_STORE, ApiError, is_api_path
from api.version import API_VERSION, API_VERSION_HEADER
from field_limits import MAX_PASSWORD_LENGTH
from room_cookies import is_same_origin_request

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
MAX_BODY_BYTES = 64 * 1024
MAX_ITEM_GROUP_BODY_BYTES = 640 * 1024


class StrictBody(BaseModel):
    """Base for request bodies: a field the model does not know is a 422."""

    model_config = ConfigDict(extra="forbid")


# A password: text, at most MAX_PASSWORD_LENGTH characters.
Password = Annotated[StrictStr, Field(max_length=MAX_PASSWORD_LENGTH)]


def _has_body(request: Request) -> bool:
    length = request.headers.get("content-length")
    return (length is not None and length != "0") or (
        "transfer-encoding" in request.headers
    )


def _is_json(request: Request) -> bool:
    media_type = request.headers.get("content-type", "").split(";", 1)[0]
    return media_type.strip().lower() == "application/json"


async def check_write_request(request: Request) -> None:
    """Router-wide dependency: writes must be same-origin and send JSON.

    Same-origin means an exact Origin match and, when sent, Sec-Fetch-Site. CORS is never enabled. A DELETE without a body is fine.
    """
    if request.method not in WRITE_METHODS:
        return
    if not is_same_origin_request(request):
        raise ApiError(403, "forbidden_origin")
    if (request.method != "DELETE" or _has_body(request)) and not _is_json(request):
        raise ApiError(415, "invalid_request", "Send a JSON body.")


async def _json_object(request: Request, max_bytes: int) -> dict[str, Any]:
    """Read one bounded JSON object (400 if it is not JSON)."""
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > max_bytes:
            raise ApiError(413, "invalid_request", "The request body is too large.")
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        raise ApiError(400, "invalid_request", "The body is not valid JSON.") from None
    if not isinstance(data, dict):
        raise ApiError(422, "invalid_request", "The body must be a JSON object.")
    return data


async def json_object(request: Request) -> dict[str, Any]:
    """Dependency: standard-sized JSON object for API requests."""
    return await _json_object(request, MAX_BODY_BYTES)


async def item_group_json_object(request: Request) -> dict[str, Any]:
    """Dependency: allow the bounded full content of a 1,000-item group."""
    return await _json_object(request, MAX_ITEM_GROUP_BODY_BYTES)


# The request body, read by the API dependencies above.
JsonBody = Annotated[dict[str, Any], Depends(json_object)]
ItemGroupJsonBody = Annotated[dict[str, Any], Depends(item_group_json_object)]


def parse_body[ModelT: BaseModel](model: type[ModelT], data: dict[str, Any]) -> ModelT:
    """Validate a JSON object against a model; wrong fields give 422."""
    try:
        return model.model_validate(data)
    except ValidationError:
        raise ApiError(422, "invalid_request") from None


class NoStoreMiddleware:
    """Pure ASGI middleware: no-store and the API version on every /api response.

    Pure ASGI (not BaseHTTPMiddleware) so streamed responses pass straight
    through.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not is_api_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        async def send_no_store(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower()
                    not in (b"cache-control", API_VERSION_HEADER.lower().encode())
                ]
                headers.append((b"cache-control", NO_STORE.encode()))
                headers.append((API_VERSION_HEADER.encode(), str(API_VERSION).encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_no_store)
