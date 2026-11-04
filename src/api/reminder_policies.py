"""Private, installation-owned reminder policy resources."""

import hashlib
from typing import Annotated, Any, ClassVar, Literal

from fastapi import APIRouter, Request
from pydantic import Field, StrictBool, StrictInt

from api.access import room_access
from api.errors import ApiError
from api.ops import Uuid
from api.reminders import (
    _check_revision,
    _require_device,
    personal_request_hash,
    run_personal_once_locked,
)
from api.requests import JsonBody, StrictBody, parse_body
from reminders import identity, policies
from reminders.rules import FixedRule, RelativeRule
from reminders.zoned_time import format_utc

router = APIRouter()


class PolicyBody(StrictBody):
    op_id: Uuid
    base_revision: Annotated[StrictInt, Field(ge=0)]
    state: Literal["inherit", "off", "replace"]
    preset: Literal["quiet", "daily_summary", "scheduled", "custom"] | None = None
    rules: list[dict[str, Any]] = Field(default_factory=list)
    summary_enabled: StrictBool = False
    summary_time: str | None = None
    action: ClassVar[str] = "replace_policy"


def _view(policy: policies.Policy) -> dict[str, Any]:
    rules = []
    for rule in policy.rules:
        if isinstance(rule, RelativeRule):
            rules.append(
                {
                    "kind": "relative",
                    "basis": rule.basis,
                    "amount": rule.amount,
                    "key": rule.key,
                }
            )
        else:
            assert isinstance(rule, FixedRule)
            rules.append(
                {
                    "kind": "fixed",
                    "id": rule.id,
                    "date": rule.date,
                    "time": rule.time,
                    "timezone": rule.timezone,
                    "instant": format_utc(rule.instant),
                    "activation": format_utc(rule.activation),
                }
            )
    return {
        "scope": policy.scope,
        "state": policy.state,
        "preset": policy.preset,
        "summary_enabled": policy.summary_enabled,
        "rules": rules,
        "revision": policy.revision,
        "activated_at": format_utc(policy.activated_at)
        if policy.activated_at
        else None,
    }


def _authorized(
    request: Request, room_id: int, scope: policies.Scope, target_id: int | None
) -> int:
    installation_id = _require_device(request)
    if identity.enrollment_row_locked(installation_id, room_id) is None:
        raise ApiError(403, "not_enrolled")
    try:
        policies.validate_target_locked(room_id, scope, target_id)
    except ValueError:
        raise ApiError(404, "not_found") from None
    return installation_id


def _get(
    slug: str, request: Request, scope: policies.Scope, target_id: int | None
) -> dict[str, Any]:
    with room_access(request, slug) as room:
        installation = _authorized(request, room.room_id, scope, target_id)
        own = policies.policy_locked(installation, room.room_id, scope, target_id)
        selected, _, _ = policies.resolve_policy_locked(
            installation, room.room_id, scope, target_id
        )
        return {"policy": _view(own), "effective": _view(selected)}


def _put(
    slug: str,
    request: Request,
    body: JsonBody,
    scope: policies.Scope,
    target_id: int | None,
) -> dict[str, Any]:
    data = parse_body(PolicyBody, body)
    digest = hashlib.sha256(
        f"{scope}:{target_id}:{personal_request_hash(data)}".encode()
    ).hexdigest()
    with room_access(request, slug, write=True) as room:
        installation = _authorized(request, room.room_id, scope, target_id)

        def run() -> dict[str, Any]:
            current = policies.policy_locked(
                installation, room.room_id, scope, target_id
            )
            _check_revision(current.revision, data.base_revision)
            try:
                updated = policies.replace_policy_locked(
                    installation,
                    room.room_id,
                    scope,
                    target_id,
                    state=data.state,
                    preset=data.preset,
                    inputs=data.rules,
                    summary_enabled=data.summary_enabled,
                    summary_time=data.summary_time,
                    now=identity.current_time(),
                )
            except ValueError as error:
                raise ApiError(422, "invalid_request", str(error)) from None
            selected, _, _ = policies.resolve_policy_locked(
                installation, room.room_id, scope, target_id
            )
            return {"policy": _view(updated), "effective": _view(selected)}

        result, _ = run_personal_once_locked(
            identity.ENROLLMENT_SCOPE,
            installation,
            room.room_id,
            data.op_id,
            digest,
            run,
        )
        return result


@router.get("/rooms/{slug}/reminders/policy")
def get_room(slug: str, request: Request) -> dict[str, Any]:
    return _get(slug, request, "room", None)


@router.put("/rooms/{slug}/reminders/policy")
def put_room(slug: str, request: Request, body: JsonBody) -> dict[str, Any]:
    return _put(slug, request, body, "room", None)


@router.get("/rooms/{slug}/reminders/lists/{target_id}/policy")
def get_list(slug: str, target_id: int, request: Request) -> dict[str, Any]:
    return _get(slug, request, "list", target_id)


@router.put("/rooms/{slug}/reminders/lists/{target_id}/policy")
def put_list(
    slug: str, target_id: int, request: Request, body: JsonBody
) -> dict[str, Any]:
    return _put(slug, request, body, "list", target_id)


@router.get("/rooms/{slug}/reminders/items/{target_id}/policy")
def get_item(slug: str, target_id: int, request: Request) -> dict[str, Any]:
    return _get(slug, request, "item", target_id)


@router.put("/rooms/{slug}/reminders/items/{target_id}/policy")
def put_item(
    slug: str, target_id: int, request: Request, body: JsonBody
) -> dict[str, Any]:
    return _put(slug, request, body, "item", target_id)
