# Installed iPhone offline acceptance (separate task)

## Goal and boundaries

Verify the installed ListR app on the owner's real iPhone, using only disposable
rooms, lists, credentials, and screenshots. This is **manual acceptance**, not
part of the automated test-suite hardening task. The owner has an iPhone but no
Mac; Safari and a reachable HTTPS test URL are sufficient for manual acceptance.
Linux Playwright WebKit and the Android emulator do not establish installed-iPhone
behavior. See [installation behavior and device checklist](../docs/home-screen-installation.md#outstanding-real-device-acceptance-checklist)
for current behavior and the broader installation cases.

This plan does not authorize exposing a server, accessing production data,
pushing, deploying, or changing `main`. The owner must approve the HTTPS tunnel
provider and public exposure, or a separate test deployment, **before** setup.
Do not use live Railway or real user data to make the phone test reachable.

## Prerequisites and setup

1. Finish and report automated/local checks and failures first; settle any
   blocking issues before requesting the owner's hands-on iPhone time.
2. Agree on a short-lived reputable HTTPS tunnel to a loopback-only local app,
   or explicitly approve a separate non-production HTTPS deployment. A Mac is
   not necessary; a Mac would only be needed for iOS Simulator/remote inspection.
3. Start the chosen candidate with a fresh disposable SQLite database and random
   test-only secrets; keep credentials out of URLs, logs, screenshots, and chat.
   Do not point the candidate at a production backup or live database.

## Manual session

Record iOS/Safari version, URL mode, exact steps, pass/fail, and limitations.
Use disposable test data and verify:

- In Safari, sign in to a room with multiple lists and meaningful item details,
  including a list never opened online. Add to Home Screen and launch the icon.
  Confirm the saved copy is ready before disconnecting.
- In airplane mode, view the already-open in-page read-only fallback. Force-close
  and relaunch the installed icon: check every list, its saved timestamp, and
  absence of editing controls. Test an existing root-launch icon if available.
- While offline, change data and revoke the room password or delete the room
  from a separate authorized session. The old copy may remain readable while
  disconnected; after reconnect, changes should refresh, and definitive denial
  should clear the matching copy. Distinguish temporary network failure from
  revocation. Record storage eviction or a shell that cannot load as a failure,
  not a softened gate.
- Shut down the tunnel/server and verify they are no longer reachable. Retain
  only test-data evidence with approved storage/handling.

Manual Safari results do not verify physical Android behavior or Railway proxy
configuration. The owner decides separately whether the evidence supports a
release; no push/deploy is part of this task.

## Progress

- [x] Separated the manual iPhone acceptance proposal from automated test hardening.
- [ ] Owner approves a specific HTTPS exposure approach and schedules the session after automated checks.
- [ ] Complete and record installed-iPhone acceptance with disposable data.
- [ ] Shut down and verify the approved exposure is closed; report remaining device limitations.
