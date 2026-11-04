# API: Personal reminder settings

Part of the [JSON API](api.md). These settings belong to **this device**
(one browser or installed app), not to the account or the room. Nothing here
is shared: room feeds, share links and live updates never carry it. Device
settings apply to every room this device is enrolled in. Delivery of reminders
is not active yet; these endpoints only store settings.

## Device and enrollment

- **Device:** a random secret, issued by the server when this device first
  enrolls. Only its sha256 hash is stored. It is never in JavaScript, a
  response body or a log.
- **Device cookie:** HTTP-only, `SameSite=Lax`, `Path=/`, no `Domain`, one
  year. HTTPS: `__Host-listapp-device` with `Secure`. Plain HTTP (local tests):
  `listapp-device` without `Secure`.
- **Enrollment:** one device in one room. It stores the hash of the room token
  that authorized it and the room's authorization version at that time.
- **Saved grant:** an enrollment is active only while that token is live,
  the room version has not changed, and the grant has not expired.
  Installation alone grants nothing. Every request still needs the room cookie.

### Expiry and renewal

Times are UTC. Expiry is checked on each request with the server clock.

- The device expires one year after it was created or last enrolled.
- A saved grant expires at the earlier of one year after the last explicit
  enrollment and one year after its authorizing room token was created.
- Only `POST …/reminders/enrollment` starts a new lifetime. Reads
  (`GET`) and PATCH never extend the device, the grant or the cookie.
- An expired device behaves as missing: it is not an installation for any
  request. An expired grant reports `needs_resume`.
- The installation expiry is checked on every grant state read, not only on the
  cookie lookup, so a grant cannot read as `active` after its device expired.
- Room tokens store no expiry. The grant bound uses the token's creation time
  plus one year, the same as the room cookie.

### Revocation

These cut the saved grant of every enrollment they affect. Nothing else changes
(settings and history are kept), and no open page is required:

- Sign-out of the room (`DELETE …/session`) or any token revocation.
- Room password change, including an admin reset. This revokes all tokens.

Signing in again does **not** resume a device. An explicit enrollment does.
Room deletion removes that room's enrollments only.

## Endpoints

All paths are under `/api/v1/rooms/{slug}/reminders`. Every route needs the
room cookie first (401 `not_authenticated` otherwise). Writes also need the
same-origin and JSON rules in [writes](api.md#writes-same-origin-rule).

| Request | Needs device cookie | Effect |
|---|---|---|
| `POST enrollment` | no (creates one) | Create or resume this device's enrollment. Sets the device cookie. |
| `GET preferences` | optional | Read this device's enrollment in the room. Never sets a cookie. |
| `PATCH preferences` | yes | Change mode, summary time or opt out of this room. |
| `GET preferences/device` | optional | Read device-wide settings, or `null`. |
| `PATCH preferences/device` | yes | Change device-wide settings. |

### Enrollment (`POST enrollment`)

Body (no other fields allowed):

- `op_id` (UUID, required): retry key, see [idempotency](#idempotency).
- `base_revision` (integer or null): `null` for a new enrollment in this
  room; otherwise the enrollment's current `revision`.
- `timezone` (IANA name): required only for a new device. Once set, the device
  zone changes only through PATCH device; a different value here is 422.
- `mode`: `quiet`, `daily_summary`, `scheduled` or `custom`. Default
  `daily_summary`. Quiet, scheduled and custom are stored choices only.
- `summary_time` (`HH:MM`): default `09:00`.

Response 200: `{"enrollment": {state, mode, summary_time, revision, activated_at}}`
with `state` `active`. Sets the device cookie (renewed).

### Enrollment settings (`GET`/`PATCH preferences`)

`GET` returns `{"enrollment": {state, mode, summary_time, revision,
activated_at}}`. Without a device cookie, or with no enrollment in this
room, `state` is `not_enrolled` and `revision` is `null`. A revoked or
expired grant reports `needs_resume`. An opted-out room reports `opted_out`.

`PATCH` body: `op_id`, `base_revision` (required), and any of `mode`,
`summary_time`, `opted_out` (only `true`). It never activates a grant; use
`POST enrollment` to resume. Returns the same `enrollment` object.

### Device settings (`GET`/`PATCH preferences/device`)

`GET` returns `{"device": null}` without a device cookie, otherwise
`{"device": {...}}`. Fields:

| Field | Value | Default |
|---|---|---|
| `revision` | integer | `1` |
| `timezone` | IANA zone | set at first enrollment |
| `all_day_time` | `HH:MM` | `09:00` |
| `quiet_hours` | `{start, end}` `HH:MM`, or `null` (off) | `22:00`–`08:00` |
| `daily_cap` | 1–50 | `10` |
| `spacing_minutes` | 1–60 | `10` |
| `paused` | boolean | `false` |
| `content_privacy` | `generic`, `counts` or `names` | `generic` |
| `overdue_repeat_days` | 1–30, or `null` (off) | `null` |

`PATCH` body: `op_id`, `base_revision` (required), and any of the fields
above. An absent field keeps its value. `quiet_hours` and
`overdue_repeat_days` accept `null` to turn them off; other fields reject
`null` (422). Quiet hours need two different times. Timezone must be a
known IANA zone: an unknown zone is 422 and never falls back to UTC.

These settings apply to every room this device is enrolled in, not to the
account. Changing a device setting does not change any room's data.

## Idempotency and revisions

- Each personal write has its own store (`reminder_processed_ops`), split by
  scope: `installation` (device settings) and `enrollment` (one room). Shared
  `op_id`s in list and item writes never collide with these.
- The hash covers the **action** (enrollment POST or preferences PATCH) and the
  body. The same `op_id` with the same body replays the stored result for that
  action. The same `op_id` for the other action, or with another body, is
  409 `op_id_reused` and changes nothing.
- A replay applies nothing again. It does not move the activation time, does
  not renew the device or grant, and sets no cookie.
- Replays refresh only the dynamic `state` (`active`, `needs_resume`,
  `opted_out`) inside the same transaction, so a grant cut since the first
  response is reported as cut. Stored `revision` and other fields stay as first
  returned.
- Revisions: a PATCH whose `base_revision` is not the current one is 409
  `revision_conflict`. Refresh and review; never last-writer-wins.
- Auth and the device cookie are checked before the op is looked up. A
  forged or expired device cookie is 403 `not_enrolled`.

**Lost first response:** a new device's first enrollment creates its cookie
only in the response. If that response is lost, the client has no device
cookie to retry with. The retry creates a second device, which is harmless
but leaves an unused installation. Clients should not invent device IDs.

## Limits and privacy

- Stored device rows: a device may enroll in at most 20 rooms, and a room
  may have at most 50 enrolled devices.
- Request bodies are at most 64 KB, and unknown fields are 422.
- The server stores the device secret only as a hash. A server operator
  with database access can still read personal settings. Do not treat
  these settings as hidden from the operator.
