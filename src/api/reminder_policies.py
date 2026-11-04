"""Private, installation-owned reminder policy resources."""

import hashlib
from typing import Annotated, Any, ClassVar, Literal

from fastapi import APIRouter, Request
from pydantic import Field, StrictBool, StrictInt, model_validator

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
from database_setup import db
from identifiers import canonical_uuid
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


def _target_locked(
    room_id: int, scope: policies.Scope, target: str | int | None
) -> int | None:
    """Resolve public UIDs without revealing targets from other rooms."""
    if scope == "room":
        return None
    if isinstance(target, int) or (isinstance(target, str) and target.isdecimal()):
        target_id = int(target)
        try:
            policies.validate_target_locked(room_id, scope, target_id)
        except ValueError:
            raise ApiError(404, "not_found") from None
        return target_id
    try:
        uid = canonical_uuid(target) if isinstance(target, str) else None
    except ValueError:
        uid = None
    if uid is None:
        raise ApiError(404, "not_found")
    if scope == "list":
        row = db.execute(
            "SELECT id FROM lists WHERE room_id = ? AND uid = ?", (room_id, uid)
        ).fetchone()
    else:
        row = db.execute(
            "SELECT items.id FROM items JOIN lists ON items.list_id = lists.id WHERE lists.room_id = ? AND items.uid = ?",
            (room_id, uid),
        ).fetchone()
    if row is None:
        raise ApiError(404, "not_found")
    return row[0]


def _get(
    slug: str, request: Request, scope: policies.Scope, target_id: str | int | None
) -> dict[str, Any]:
    with room_access(request, slug) as room:
        if (
            identity.enrollment_row_locked(_require_device(request), room.room_id)
            is None
        ):
            raise ApiError(403, "not_enrolled")
        target_id = _target_locked(room.room_id, scope, target_id)
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
    target_id: str | int | None,
) -> dict[str, Any]:
    data = parse_body(PolicyBody, body)
    with room_access(request, slug, write=True) as room:
        if (
            identity.enrollment_row_locked(_require_device(request), room.room_id)
            is None
        ):
            raise ApiError(403, "not_enrolled")
        target_id = _target_locked(room.room_id, scope, target_id)
        installation = _authorized(request, room.room_id, scope, target_id)
        digest = hashlib.sha256(
            f"{scope}:{target_id}:{personal_request_hash(data)}".encode()
        ).hexdigest()

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
def get_list(slug: str, target_id: str, request: Request) -> dict[str, Any]:
    return _get(slug, request, "list", target_id)


@router.put("/rooms/{slug}/reminders/lists/{target_id}/policy")
def put_list(
    slug: str, target_id: str, request: Request, body: JsonBody
) -> dict[str, Any]:
    return _put(slug, request, body, "list", target_id)


@router.get("/rooms/{slug}/reminders/items/{target_id}/policy")
def get_item(slug: str, target_id: str, request: Request) -> dict[str, Any]:
    return _get(slug, request, "item", target_id)


@router.put("/rooms/{slug}/reminders/items/{target_id}/policy")
def put_item(
    slug: str, target_id: str, request: Request, body: JsonBody
) -> dict[str, Any]:
    return _put(slug, request, body, "item", target_id)


class PreviewDraft(StrictBody):
    state: Literal["inherit", "off", "replace"]
    preset: Literal["quiet", "daily_summary", "scheduled", "custom"] | None = None
    rules: list[dict[str, Any]] = Field(default_factory=list, max_length=5)
    summary_enabled: StrictBool = False


class PreviewBody(StrictBody):
    item_id: Annotated[StrictInt, Field(gt=0)] | None = None
    item_uid: Uuid | None = None

    @model_validator(mode="after")
    def one_target(self):
        if (self.item_id is None) == (self.item_uid is None):
            raise ValueError("Provide exactly one item identifier")
        return self

    draft: PreviewDraft | None = None


@router.post("/rooms/{slug}/reminders/preview")
def post_preview(slug: str, request: Request, body: JsonBody) -> dict[str, Any]:
    from dataclasses import replace
    from uuid import NAMESPACE_URL, uuid5

    from database_setup import db
    from reminders.preview import QuietWindow, preview_item
    from reminders.rules import normalize_rules

    data = parse_body(PreviewBody, body)
    with room_access(request, slug) as room:
        if (
            identity.enrollment_row_locked(_require_device(request), room.room_id)
            is None
        ):
            raise ApiError(403, "not_enrolled")
        item_id = _target_locked(room.room_id, "item", data.item_uid or data.item_id)
        assert item_id is not None
        installation = _authorized(request, room.room_id, "item", item_id)
        now = identity.current_time()
        effective = policies.effective_policy_locked(
            installation, room.room_id, item_id, now=now
        )
        provisional: set[str] = set()
        if data.draft is not None:
            draft = data.draft
            own = policies.policy_locked(installation, room.room_id, "item", item_id)
            if draft.state != "replace":
                if draft.preset is not None or draft.rules or draft.summary_enabled:
                    raise ApiError(
                        422,
                        "invalid_request",
                        "Off/inherit takes no preset, rules or summary",
                    )
                rules = ()
                summary = False
            elif draft.preset == "custom":
                counter = 0

                def provisional_id() -> str:
                    nonlocal counter
                    counter += 1
                    result = str(
                        uuid5(
                            NAMESPACE_URL,
                            f"preview:{installation}:{room.room_id}:{item_id}:{counter}",
                        )
                    )
                    provisional.add(result)
                    return result

                try:
                    rules = normalize_rules(
                        draft.rules,
                        existing_rules=tuple(
                            r for r in own.rules if isinstance(r, FixedRule)
                        ),
                        now=now,
                        make_rule_id=provisional_id,
                    )
                except ValueError as error:
                    raise ApiError(422, "invalid_request", str(error)) from None
                summary = draft.summary_enabled
            elif draft.preset in ("quiet", "daily_summary", "scheduled"):
                if draft.rules or draft.summary_enabled:
                    raise ApiError(
                        422,
                        "invalid_request",
                        "Only custom accepts rules and summary_enabled",
                    )
                rules = policies.SCHEDULED if draft.preset == "scheduled" else ()
                summary = draft.preset == "daily_summary"
            else:
                raise ApiError(
                    422, "invalid_request", "A replacement requires a preset"
                )
            enrollment = next(
                a for a in effective.relative_activations if a.source == "enrollment"
            )
            selected_scope = "item"
            activations = [enrollment, policies.Activation("item", now)]
            state, preset = draft.state, draft.preset
            if draft.state == "inherit":
                list_id = db.execute(
                    "SELECT list_id FROM items WHERE id = ?", (item_id,)
                ).fetchone()[0]
                selected, _, parent_cutoffs = policies.resolve_policy_locked(
                    installation, room.room_id, "list", list_id
                )
                activations = [policies.Activation("item", now), *parent_cutoffs]
                selected_scope, state, preset, rules, summary = (
                    selected.scope,
                    selected.state,
                    selected.preset,
                    selected.rules,
                    selected.summary_enabled,
                )
            relative = (
                *activations,
                *(
                    a
                    for a in effective.relative_activations
                    if a.source in ("cycle", "device_anchor")
                ),
            )
            summary_cutoffs = (
                *activations,
                *(
                    a
                    for a in effective.summary_activations
                    if a.source in ("summary_time", "device_timezone")
                ),
            )
            disabled = tuple(x for x in effective.disabled_reasons if x != "policy_off")
            if state == "off" or preset == "quiet":
                disabled += ("policy_off",)
            effective = replace(
                effective,
                source=selected_scope,
                state=state,
                preset=preset,
                rules=rules,
                summary_enabled=summary,
                relative_activations=relative,
                summary_activations=summary_cutoffs,
                disabled_reasons=disabled,
            )
        device = identity.installation_settings_locked(installation)
        quiet = (
            QuietWindow(device["quiet_start"], device["quiet_end"])
            if device["quiet_start"] is not None
            else None
        )
        result = preview_item(effective, now=now, quiet=quiet)
        return {
            "source": effective.source,
            "state": effective.state,
            "preset": effective.preset,
            "timezone": effective.timezone,
            "disabled_reasons": list(result.disabled_reasons),
            "provisional_fixed_ids": sorted(provisional),
            "entries": [
                {
                    "kind": e.kind,
                    "instant": format_utc(e.instant),
                    "keys": list(e.keys),
                    "deferred_until": format_utc(e.deferred_until)
                    if e.deferred_until
                    else None,
                    "local_day": e.local_day,
                }
                for e in result.entries
            ],
        }
