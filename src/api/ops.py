"""Write operations: `POST /api/v1/rooms/{slug}/ops` (docs/api.md, "Writing").

One operation per request. Each op type has a body model (picked by `type`)
and a handler that runs inside the room's write transaction. A handler
returns the `result`, or raises OpRejected when a business rule says no.
Rejected ops change nothing, but their response is stored like an applied
one, so a retry gets the same answer.
"""

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date as calendar_date
from typing import Annotated, Any, ClassVar, Literal

from fastapi import APIRouter, Request
from pydantic import (
    AfterValidator,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from api.access import room_access, share_access
from api.errors import ApiError
from api.idempotency import Response, request_hash, run_once_locked
from api.requests import JsonBody, StrictBody
from database_crud import (
    CountLimitReached,
    add_or_restore_item_locked,
    adjust_item_quantity_locked,
    change_list_tag_locked,
    create_or_find_list_locked,
    delete_item_locked,
    delete_list_locked,
    get_item_changed_seq_locked,
    get_item_state_locked,
    get_item_uid_locked,
    get_list_changed_seq_locked,
    get_list_state_locked,
    get_list_uid_locked,
    get_room_seq_locked,
    get_share_seq_locked,
    item_id_for_uid_locked,
    list_id_for_uid_locked,
    normalize_completion_time,
    normalize_display_name,
    normalize_item_name,
    rename_list_if_unique_locked,
    rename_list_tag_locked,
    rename_room_locked,
    restore_deleted_item_locked,
    savepoint_locked,
    set_list_tag_color_locked,
    stored_due_schedule,
    toggle_item_active_tag_locked,
    uid_in_use_locked,
    update_item_details_locked,
    update_item_done_locked,
    update_list_tag_settings_locked,
    update_list_visibility_settings_locked,
)
from field_limits import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_TAG_COLOR,
    MAX_TAG_LENGTH,
    too_long_message,
)
from identifiers import canonical_uuid
from item_visibility import (
    DEFAULT_HIDE_DONE_AGE_DAYS,
    DEFAULT_HIDE_DONE_MODE,
    DEFAULT_HIDE_DONE_RECENT_COUNT,
    parse_completion_time,
    validate_visibility_settings,
)
from live_updates import notify_room_changed
from reminders.due_schedule import CLOCK_TIME, DueSchedule, merge_due_edit
from reminders.zoned_time import TimeZoneUnavailable

router = APIRouter()

# Outcome of item.add when the name is already on the list.
STATUS_DUPLICATE_ACTIVE = "duplicate_active"


# A UUID string in its lowercase, hyphenated form.
Uuid = Annotated[StrictStr, AfterValidator(canonical_uuid)]

# Bounds quantities and deltas far from SQLite's 64-bit integer limit.
MAX_QUANTITY = 1_000_000
# Below 1 is saved as 1.
Quantity = Annotated[StrictInt, Field(ge=-MAX_QUANTITY, le=MAX_QUANTITY)]
BaseSeq = Annotated[StrictInt, Field(ge=0)]


def _completion_time(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_completion_time(value)
    if normalized is None:
        raise ValueError("completed_at is not a readable time")
    return normalized


# An ISO 8601 time, stored as UTC with Z.
CompletedAt = Annotated[StrictStr | None, AfterValidator(_completion_time)]

_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _item_date(value: str | None) -> str | None:
    """A real calendar day as `YYYY-MM-DD`; None for no date."""
    if value is None:
        return None
    if not _ISO_DATE.fullmatch(value):
        raise ValueError("date must be YYYY-MM-DD")
    try:
        calendar_date.fromisoformat(value)
    except ValueError:
        raise ValueError("date is not a real day") from None
    return value


# An item's optional date. Null clears it; a missing field keeps it.
ItemDate = Annotated[StrictStr | None, AfterValidator(_item_date)]


def _due_time(value: str | None) -> str | None:
    """A 24-hour time as `HH:MM`; None clears it."""
    if value is None:
        return None
    if not CLOCK_TIME.fullmatch(value):
        raise ValueError("time must be HH:MM")
    return value


# An item's optional due time (see reminders/due_schedule.py). Null clears it.
ItemDueTime = Annotated[StrictStr | None, AfterValidator(_due_time)]
# An IANA zone name, such as Europe/Oslo. Null clears it.
ItemDueTimezone = Annotated[StrictStr | None, Field(max_length=64)]


def _added_time(value: str | None) -> str | None:
    """An add time as stored: UTC with milliseconds and Z, like created_at."""
    if value is None:
        return None
    parsed = parse_completion_time(value)
    if parsed is None:
        raise ValueError("added_at is not a readable time")
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


# How often an item was added, and when it was last added (see database_crud).
AddCount = Annotated[StrictInt, Field(ge=1)]
AddedAt = Annotated[StrictStr | None, AfterValidator(_added_time)]


class Op(StrictBody):
    op_id: Uuid
    # Optional fields added after ops were first stored. An unset (null) one
    # is left out of the request hash, so a retry of an older op keeps its hash.
    hash_omit_if_null: ClassVar[frozenset[str]] = frozenset()


class RoomRename(Op):
    type: Literal["room.rename"]
    name: StrictStr


class ListCreate(Op):
    type: Literal["list.create"]
    name: StrictStr
    uid: Uuid | None = None


class ListRename(Op):
    type: Literal["list.rename"]
    list_uid: Uuid
    name: StrictStr
    # The list's changed_seq the page saw (see _check_base_seq).
    base_seq: BaseSeq


class ListDelete(Op):
    type: Literal["list.delete"]
    list_uid: Uuid


class ListTagAdd(Op):
    type: Literal["list.tag_add"]
    list_uid: Uuid
    tag: StrictStr


class ListTagRemove(Op):
    type: Literal["list.tag_remove"]
    list_uid: Uuid
    tag: StrictStr


class ListVisibility(Op):
    type: Literal["list.visibility"]
    list_uid: Uuid
    mode: StrictStr | None = None
    age_days: StrictInt | None = None
    recent_count: StrictInt | None = None

    @model_validator(mode="after")
    def _check_ranges(self) -> "ListVisibility":
        if self.mode is None and self.age_days is None and self.recent_count is None:
            raise ValueError("Send at least one setting")
        # Fields not sent are checked when merged with the stored values.
        validate_visibility_settings(
            DEFAULT_HIDE_DONE_MODE if self.mode is None else self.mode,
            DEFAULT_HIDE_DONE_AGE_DAYS if self.age_days is None else self.age_days,
            DEFAULT_HIDE_DONE_RECENT_COUNT
            if self.recent_count is None
            else self.recent_count,
        )
        return self


class ListTagSettings(Op):
    type: Literal["list.tag_settings"]
    list_uid: Uuid
    mode: Literal["single", "multi"] | None = None
    show_on_items: StrictBool | None = None
    only_item_tags: StrictBool | None = None

    @model_validator(mode="after")
    def _check_something_sent(self) -> "ListTagSettings":
        if (
            self.mode is None
            and self.show_on_items is None
            and self.only_item_tags is None
        ):
            raise ValueError("Send at least one setting")
        return self


def _tag_color(value: int | None) -> int | None:
    if value is not None and not 0 <= value <= MAX_TAG_COLOR:
        raise ValueError(f"color must be from 0 to {MAX_TAG_COLOR}")
    return value


# A tag's color number, or null for the default color.
TagColor = Annotated[StrictInt | None, AfterValidator(_tag_color)]


class ListTagColor(Op):
    type: Literal["list.tag_color"]
    list_uid: Uuid
    tag: StrictStr
    color: TagColor


class ListTagRename(Op):
    type: Literal["list.tag_rename"]
    list_uid: Uuid
    tag: StrictStr
    new_tag: StrictStr


class ItemAdd(Op):
    type: Literal["item.add"]
    list_uid: Uuid
    name: StrictStr
    uid: Uuid | None = None


class ItemOp(Op):
    list_uid: Uuid
    item_uid: Uuid


class ItemSetDone(ItemOp):
    type: Literal["item.set_done"]
    done: StrictBool
    # Optional: without it the last write wins.
    base_seq: BaseSeq | None = None

    hash_omit_if_null: ClassVar[frozenset[str]] = frozenset({"base_seq"})


class ItemQuantityDelta(ItemOp):
    type: Literal["item.quantity_delta"]
    delta: Quantity


class ItemEdit(ItemOp):
    type: Literal["item.edit"]
    name: StrictStr
    description: StrictStr
    quantity: Quantity | None = None
    # Not sent: kept. Sent as null: cleared. See item_edit.
    date: ItemDate = None
    due_time: ItemDueTime = None
    due_timezone: ItemDueTimezone = None
    # The item's changed_seq the page saw (see _check_base_seq).
    base_seq: BaseSeq

    hash_omit_if_null: ClassVar[frozenset[str]] = frozenset({"date"})
    hash_omit_if_unsent: ClassVar[frozenset[str]] = frozenset(
        {"due_time", "due_timezone"}
    )


class ItemToggleTag(ItemOp):
    type: Literal["item.toggle_tag"]
    tag: StrictStr
    # Optional: the wanted state. Without it the tag is toggled.
    active: StrictBool | None = None

    hash_omit_if_null: ClassVar[frozenset[str]] = frozenset({"active"})


class ItemDelete(ItemOp):
    type: Literal["item.delete"]


class ItemRestore(Op):
    type: Literal["item.restore"]
    list_uid: Uuid
    uid: Uuid | None = None
    name: StrictStr
    done: StrictBool
    tags: list[StrictStr]
    description: StrictStr
    quantity: Quantity
    completed_at: CompletedAt
    date: ItemDate = None
    due_time: ItemDueTime = None
    due_timezone: ItemDueTimezone = None
    # Kept from the deleted item. Not sent (an older page): 1 and no time.
    add_count: AddCount | None = None
    added_at: AddedAt = None

    hash_omit_if_null: ClassVar[frozenset[str]] = frozenset(
        {"date", "add_count", "added_at"}
    )
    hash_omit_if_unsent: ClassVar[frozenset[str]] = frozenset(
        {"due_time", "due_timezone"}
    )


AnyOp = Annotated[
    RoomRename
    | ListCreate
    | ListRename
    | ListDelete
    | ListTagAdd
    | ListTagRemove
    | ListTagSettings
    | ListTagColor
    | ListTagRename
    | ListVisibility
    | ItemAdd
    | ItemSetDone
    | ItemQuantityDelta
    | ItemEdit
    | ItemToggleTag
    | ItemDelete
    | ItemRestore,
    Field(discriminator="type"),
]
_OPS = TypeAdapter(AnyOp)


def parse_op(data: dict[str, Any]) -> AnyOp:
    """Validate an op body; unknown `type` or wrong fields give 422."""
    try:
        return _OPS.validate_python(data)
    except ValidationError:
        raise ApiError(422, "invalid_request") from None


class OpRejected(Exception):
    """A business rule said no. Shown to the user; nothing is changed.

    `fields` are extra keys for the rejected answer (for example the uid of
    the item that already exists).
    """

    def __init__(self, code: str, message: str, **fields: Any) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.fields = fields


# Messages shown to the user.
LIST_UNAVAILABLE = "The list is no longer available."
ITEM_NOT_FOUND = "The item is no longer available."
EMPTY_NAME = "Name cannot be empty"
UNDO_NAME_TAKEN = "Cannot undo: item name already exists"
CHANGED_MEANWHILE = "Someone else changed this meanwhile."
UNKNOWN_TAG = "The tag is not on this list."
DUE_PARTS = (
    "A due time needs a date and a time zone; a time zone needs a due time. "
    "Clearing the date clears both."
)
TIME_ZONE_UNAVAILABLE = "This time zone is not available on this server."


@dataclass(frozen=True)
class OpScope:
    """What an op may touch: a whole room, or one list through a share link."""

    room_id: int
    # Set for share links: no other list of the room is reachable.
    shared_list_id: int | None = None

    def list_id(self, list_uid: str) -> int:
        list_id = list_id_for_uid_locked(self.room_id, list_uid)
        if list_id is None or (
            self.shared_list_id is not None and list_id != self.shared_list_id
        ):
            # Deleted, or in another room (or not the shared list): the client
            # cannot tell which.
            raise OpRejected("list_unavailable", LIST_UNAVAILABLE)
        return list_id


def _list_item_id(list_id: int, item_uid: str) -> int:
    item_id = item_id_for_uid_locked(list_id, item_uid)
    if item_id is None:
        # Deleted, or in another list.
        raise OpRejected("item_not_found", ITEM_NOT_FOUND)
    return item_id


def _item_found(matched: bool) -> None:
    if not matched:
        raise OpRejected("item_not_found", ITEM_NOT_FOUND)


def _check_base_seq(
    base_seq: int | None, changed_seq: int, *, wanted_already_stored: bool
) -> None:
    """Refuse a set from a page that is behind, unless the row already has it.

    `changed_seq` is the row's current value. Someone changed the row after the
    page's `base_seq` and the stored value differs from what this op wants:
    the op is rejected. If the stored value already matches, the op is applied.
    Without `base_seq` the last write wins.
    """
    if base_seq is None or changed_seq <= base_seq or wanted_already_stored:
        return
    raise OpRejected("changed_meanwhile", CHANGED_MEANWHILE)


def _within_limit(what: str, text: str, limit: int) -> str:
    message = too_long_message(what, text, limit)
    if message:
        raise OpRejected("too_long", message)
    return text


def _item_name(raw: str) -> str:
    name = normalize_item_name(raw)
    if not name:
        raise OpRejected("invalid_name", EMPTY_NAME)
    return _within_limit("Name", name, MAX_NAME_LENGTH)


def _display_name(raw: str) -> str:
    name = normalize_display_name(raw)
    if not name:
        raise OpRejected("invalid_name", EMPTY_NAME)
    return _within_limit("Name", name, MAX_NAME_LENGTH)


def _tag(raw: str) -> str:
    # Trimmed and nonempty, like a list name.
    tag = normalize_display_name(raw)
    if not tag:
        raise OpRejected("invalid_name", EMPTY_NAME)
    return _within_limit("Tag", tag, MAX_TAG_LENGTH)


def _description(text: str) -> str:
    return _within_limit("Description", text, MAX_DESCRIPTION_LENGTH)


def clamp_quantity(quantity: int) -> int:
    """Quantities are whole numbers from 1 up."""
    return max(1, int(quantity))


def _new_uid(uid: str | None) -> str | None:
    if uid is not None and uid_in_use_locked(uid):
        raise ApiError(422, "invalid_request", "This uid is already used.")
    return uid


def room_rename(scope: OpScope, op: RoomRename) -> dict[str, Any]:
    # Room names need not be unique.
    rename_room_locked(scope.room_id, _display_name(op.name))
    return {}


def list_create(scope: OpScope, op: ListCreate) -> dict[str, Any]:
    uid = _new_uid(op.uid)
    list_id, slug, created = create_or_find_list_locked(
        _display_name(op.name), scope.room_id, uid=uid
    )
    return {"list_uid": get_list_uid_locked(list_id), "slug": slug, "created": created}


def list_rename(scope: OpScope, op: ListRename) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    name = _display_name(op.name)
    stored_name, changed_seq = get_list_state_locked(list_id)
    _check_base_seq(op.base_seq, changed_seq, wanted_already_stored=stored_name == name)
    if not rename_list_if_unique_locked(list_id, scope.room_id, name):
        raise OpRejected("duplicate_name", f"'{name}' already exists in this room")
    return {"changed_seq": get_list_changed_seq_locked(list_id)}


def list_delete(scope: OpScope, op: ListDelete) -> dict[str, Any]:
    delete_list_locked(scope.list_id(op.list_uid))
    return {}


def list_tag_add(scope: OpScope, op: ListTagAdd) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    change_list_tag_locked(list_id, _tag(op.tag), add=True)
    return {"changed_seq": get_list_changed_seq_locked(list_id)}


def list_tag_remove(scope: OpScope, op: ListTagRemove) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    change_list_tag_locked(list_id, op.tag, add=False)
    return {"changed_seq": get_list_changed_seq_locked(list_id)}


def list_tag_settings(scope: OpScope, op: ListTagSettings) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    update_list_tag_settings_locked(
        list_id,
        mode=op.mode,
        show_on_items=op.show_on_items,
        only_item_tags=op.only_item_tags,
    )
    return {"changed_seq": get_list_changed_seq_locked(list_id)}


def list_tag_color(scope: OpScope, op: ListTagColor) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    if not set_list_tag_color_locked(list_id, op.tag, op.color):
        raise OpRejected("unknown_tag", UNKNOWN_TAG)
    return {"changed_seq": get_list_changed_seq_locked(list_id)}


def list_tag_rename(scope: OpScope, op: ListTagRename) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    new_tag = _tag(op.new_tag)
    outcome = rename_list_tag_locked(list_id, op.tag, new_tag)
    if outcome == "missing":
        raise OpRejected("unknown_tag", UNKNOWN_TAG)
    if outcome == "duplicate":
        raise OpRejected("duplicate_name", f"'{new_tag}' already exists")
    return {"changed_seq": get_list_changed_seq_locked(list_id)}


def list_visibility(scope: OpScope, op: ListVisibility) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    update_list_visibility_settings_locked(
        list_id, mode=op.mode, age_days=op.age_days, recent_count=op.recent_count
    )
    return {"changed_seq": get_list_changed_seq_locked(list_id)}


def item_add(scope: OpScope, op: ItemAdd) -> dict[str, Any]:
    uid = _new_uid(op.uid)
    list_id = scope.list_id(op.list_uid)
    name = _item_name(op.name)
    outcome, item_id = add_or_restore_item_locked(name, list_id, uid=uid)
    if outcome == STATUS_DUPLICATE_ACTIVE:
        raise OpRejected(
            "duplicate_active",
            f"'{name}' is already on the list",
            item_uid=get_item_uid_locked(item_id),
        )
    return {
        "item_uid": get_item_uid_locked(item_id),
        "outcome": outcome,
        "changed_seq": get_item_changed_seq_locked(item_id),
    }


def item_set_done(scope: OpScope, op: ItemSetDone) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    item_id = _list_item_id(list_id, op.item_uid)
    stored = get_item_state_locked(item_id)
    _check_base_seq(
        op.base_seq,
        stored["changed_seq"],
        wanted_already_stored=stored["done"] == op.done,
    )
    _item_found(update_item_done_locked(item_id, list_id, op.done))
    return {"changed_seq": get_item_changed_seq_locked(item_id)}


def item_quantity_delta(scope: OpScope, op: ItemQuantityDelta) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    item_id = _list_item_id(list_id, op.item_uid)
    _item_found(adjust_item_quantity_locked(item_id, list_id, op.delta))
    return {"changed_seq": get_item_changed_seq_locked(item_id)}


def _due_schedule(
    stored: DueSchedule,
    *,
    date_given: bool,
    date: str | None,
    time_given: bool,
    time: str | None,
    zone_given: bool,
    zone: str | None,
) -> DueSchedule:
    """The schedule an op wants; a rule it breaks is a rejection."""
    try:
        return merge_due_edit(
            stored,
            date_given=date_given,
            date=date,
            time_given=time_given,
            time=time,
            zone_given=zone_given,
            zone=zone,
        )
    except ValueError:
        raise OpRejected("invalid_due", DUE_PARTS) from None


def _due_resolved(schedule: DueSchedule) -> None:
    """Check that a schedule's zone is known, before anything is written."""
    try:
        schedule.due_at()
    except TimeZoneUnavailable:
        raise OpRejected("time_zone_unavailable", TIME_ZONE_UNAVAILABLE) from None
    except ValueError:
        raise OpRejected("invalid_due", DUE_PARTS) from None


def item_edit(scope: OpScope, op: ItemEdit) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    item_id = _list_item_id(list_id, op.item_uid)
    name = _item_name(op.name)
    description = _description((op.description or "").strip())
    quantity = None if op.quantity is None else clamp_quantity(op.quantity)
    # A date, time or zone that was not sent is kept and is not part of what
    # the op wants.
    date_given = "date" in op.model_fields_set
    time_given = "due_time" in op.model_fields_set
    zone_given = "due_timezone" in op.model_fields_set
    stored = get_item_state_locked(item_id)
    schedule = _due_schedule(
        stored_due_schedule(stored),
        date_given=date_given,
        date=op.date,
        time_given=time_given,
        time=op.due_time,
        zone_given=zone_given,
        zone=op.due_timezone,
    )
    # A quantity that was not sent is not part of what the op wants.
    wanted_already_stored = (
        stored["name"] == name
        and stored["description"] == description
        and (quantity is None or stored["quantity"] == quantity)
        and schedule == stored_due_schedule(stored)
    )
    _check_base_seq(
        op.base_seq, stored["changed_seq"], wanted_already_stored=wanted_already_stored
    )
    # Only a changed schedule needs its zone: an unchanged one is not resolved.
    if schedule != stored_due_schedule(stored):
        _due_resolved(schedule)
    status = update_item_details_locked(
        item_id,
        list_id,
        name,
        description,
        quantity,
        date_given=date_given,
        date=op.date,
        due_time_given=time_given,
        due_time=op.due_time,
        due_timezone_given=zone_given,
        due_timezone=op.due_timezone,
    )
    if status == "duplicate":
        raise OpRejected("duplicate_name", f"'{name}' already exists")
    _item_found(status == "saved")
    return {"changed_seq": get_item_changed_seq_locked(item_id)}


def item_toggle_tag(scope: OpScope, op: ItemToggleTag) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    item_id = _list_item_id(list_id, op.item_uid)
    _item_found(
        toggle_item_active_tag_locked(item_id, list_id, op.tag, active=op.active)
    )
    return {"changed_seq": get_item_changed_seq_locked(item_id)}


def item_delete(scope: OpScope, op: ItemDelete) -> dict[str, Any]:
    list_id = scope.list_id(op.list_uid)
    item_id = item_id_for_uid_locked(list_id, op.item_uid)
    if item_id is not None:
        delete_item_locked(item_id, list_id)
    # Already gone (or in another list): nothing to do, not an error.
    return {}


def item_restore(scope: OpScope, op: ItemRestore) -> dict[str, Any]:
    uid = _new_uid(op.uid)
    list_id = scope.list_id(op.list_uid)
    # The due time and zone are checked and resolved before the restore writes.
    schedule = _due_schedule(
        DueSchedule(),
        date_given=True,
        date=op.date,
        time_given=True,
        time=op.due_time,
        zone_given=True,
        zone=op.due_timezone,
    )
    _due_resolved(schedule)
    item_id = restore_deleted_item_locked(
        list_id,
        _item_name(op.name),
        op.done,
        op.tags,
        _description(op.description),
        clamp_quantity(op.quantity),
        completed_at=op.completed_at,
        uid=uid,
        date=op.date,
        add_count=1 if op.add_count is None else op.add_count,
        added_at=op.added_at,
        due_time=op.due_time,
        due_timezone=op.due_timezone,
    )
    if item_id is None:
        raise OpRejected("undo_name_taken", UNDO_NAME_TAKEN)
    return {
        "item_uid": get_item_uid_locked(item_id),
        "changed_seq": get_item_changed_seq_locked(item_id),
    }


HANDLERS: dict[str, Callable[[OpScope, Any], dict[str, Any]]] = {
    "room.rename": room_rename,
    "list.create": list_create,
    "list.rename": list_rename,
    "list.delete": list_delete,
    "list.tag_add": list_tag_add,
    "list.tag_remove": list_tag_remove,
    "list.tag_settings": list_tag_settings,
    "list.tag_color": list_tag_color,
    "list.tag_rename": list_tag_rename,
    "list.visibility": list_visibility,
    "item.add": item_add,
    "item.set_done": item_set_done,
    "item.quantity_delta": item_quantity_delta,
    "item.edit": item_edit,
    "item.toggle_tag": item_toggle_tag,
    "item.delete": item_delete,
    "item.restore": item_restore,
}


# What a share link may do: everything inside its list (as on the
# public page), nothing to the room or to the list itself.
SHARE_OP_TYPES = frozenset(
    {
        "list.tag_add",
        "list.tag_remove",
        "list.tag_settings",
        "list.tag_color",
        "list.tag_rename",
        "list.visibility",
        "item.add",
        "item.set_done",
        "item.quantity_delta",
        "item.edit",
        "item.toggle_tag",
        "item.delete",
        "item.restore",
    }
)


def _answer_seq(scope: OpScope) -> int:
    """The seq an answer carries: the room's, or the shared list's for a link."""
    if scope.shared_list_id is not None:
        return get_share_seq_locked(scope.shared_list_id)
    return get_room_seq_locked(scope.room_id)


def _rejected(scope: OpScope, op: Any, rejection: OpRejected) -> Response:
    return {
        "op_id": op.op_id,
        "status": "rejected",
        "code": rejection.code,
        "message": rejection.message,
        **rejection.fields,
        "seq": _answer_seq(scope),
    }


def _apply_locked(scope: OpScope, op: Any) -> Response:
    try:
        with savepoint_locked():
            result = HANDLERS[op.type](scope, op)
    except OpRejected as rejection:
        return _rejected(scope, op, rejection)
    except CountLimitReached as limit:
        # A count limit is reached (nothing was written: the savepoint rolled back).
        return _rejected(scope, op, OpRejected("too_many", str(limit)))
    return {
        "op_id": op.op_id,
        "status": "applied",
        "result": result,
        "seq": _answer_seq(scope),
    }


def _run_write_op(
    op: Op,
    access: AbstractContextManager[Any],
    scope_for: Callable[[Any], OpScope],
) -> Response:
    """Run one op in the access transaction, then tell live streams of a change.

    `access` checks the caller and yields the room or share; `scope_for` turns
    that into what the op may touch.
    """
    body_hash = request_hash(op)
    with access as target:
        scope = scope_for(target)
        response, replayed = run_once_locked(
            target.room_id, op.op_id, body_hash, lambda: _apply_locked(scope, op)
        )
    # After the commit, outside the database lock.
    if not replayed and response["status"] == "applied":
        notify_room_changed(target.room_id)
    return response


@router.post("/rooms/{slug}/ops")
def post_op(slug: str, request: Request, body: JsonBody) -> Response:
    op = parse_op(body)
    return _run_write_op(
        op,
        room_access(request, slug, write=True),
        lambda room: OpScope(room.room_id),
    )


def run_share_op(token: str, body: dict[str, Any]) -> Response:
    """`POST /api/v1/share/{token}/ops`: one op on the shared list only."""
    op = parse_op(body)
    if op.type not in SHARE_OP_TYPES:
        raise ApiError(422, "invalid_request", "A share link cannot do this.")
    return _run_write_op(
        op,
        share_access(token, write=True),
        lambda share: OpScope(share.room_id, shared_list_id=share.list_id),
    )
