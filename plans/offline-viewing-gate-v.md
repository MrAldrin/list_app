# Offline viewing: Gate V owner review

Lifecycle: temporary

Read-only offline viewing is built and tested locally. Nothing is deployed. This
guide is for your review. No iPhone check has been done.

## Ready to review

- Saved read-only views: room, room list, private list, share page.
- Disabled edits, local search in the Add field, notices, offline `lastRoom`.
- Reconnect and resume revalidation; logout and revocation clearing.
- Details: [offline viewing](../docs/offline-viewing.md). Evidence:
  [validation record](../docs/background/offline-viewing-validation.md).

## Run it locally

- Build and serve: `(cd frontend && npm run build)` then
  `uv run python src/main.py` (see the [README](../README.md)).
- For the phone (HTTPS needed): `uv run python scripts/serve_svelte_local.py`.
  See [HTTPS on the phone](../docs/local-network-testing.md#https-on-the-phone).
- Checks: `uv run pytest -q`; browser suite per
  [browser testing](../docs/browser-testing.md).

## iPhone checklist (Safari, then home screen)

Record the iOS version: ______

- [x] Open the app over HTTPS and sign in to a room.
- [x] Open a room list, a private list and a share link online.
- [x] Add the app to the home screen.
- [x] Airplane mode: close and reopen from Safari. Saved views appear.
- [x] Airplane mode: close and reopen from the home-screen icon.
- [x] Navigate between room, lists and the share page offline.
- [x] Type in the Add field: the list filters.
- [x] Edit controls are disabled and say why.
- [ ] Go online without reloading, and change an item on another device: it appears.
- [ ] Log out (online, then also offline): saved data is gone after reload.
- [ ] Open a revoked share link or reset the room password: saved data clears.
- [ ] Note anything odd (wording, timing, layout). 2026-10-12: three offline
  messages at once and a missing space; fixed with one offline notice. Recheck it.

## Blockers before the first production rollout

- Both blockers are built and pass the local checks; the owner review is still
  open. See [offline viewing](../docs/offline-viewing.md#after-a-deploy).
- New versions only reached phones after every copy of the app was closed.
  Fixed locally (switch on open); iPhone recheck left:
  [offline version updates](offline-version-updates.md).
- Real-device behaviour of that banner is a [backlog](backlog.md) manual check.
  Deployment needs separate approval.

## Progress

- [x] Local implementation and tests done
- [ ] Owner iPhone checklist done
- [ ] Owner accepts or requests changes
