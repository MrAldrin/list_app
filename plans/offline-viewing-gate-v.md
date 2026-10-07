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

- [ ] Open the app over HTTPS and sign in to a room.
- [ ] Open a room list, a private list and a share link online.
- [ ] Add the app to the home screen.
- [ ] Airplane mode: close and reopen from Safari. Saved views appear.
- [ ] Airplane mode: close and reopen from the home-screen icon.
- [ ] Navigate between room, lists and the share page offline.
- [ ] Type in the Add field: the list filters.
- [ ] Edit controls are disabled and say why.
- [ ] Go online without reloading, and change an item on another device: it appears.
- [ ] Log out (online, then also offline): saved data is gone after reload.
- [ ] Open a revoked share link or reset the room password: saved data clears.
- [ ] Note anything odd (wording, timing, layout).

## Blockers before the first production rollout

- Both blockers are built but NOT yet verified or reviewed (bookmark
  `offline-launch-blockers-wip`). The full browser suite still has 1 failure
  and 3 WebKit errors to diagnose. See
  [offline viewing](../docs/offline-viewing.md#after-a-deploy).
- Real-device behaviour of that banner is a [backlog](backlog.md) manual check.
  Deployment needs separate approval.

## Progress

- [x] Local implementation and tests done
- [ ] Owner iPhone checklist done
- [ ] Owner accepts or requests changes
