# Browser verification repair

## Status

Investigation is in progress under local task `lr-1nn`. No result is accepted
or deployed. The current task record carries approval for bounded product
repairs. Older no-product-approval statements in the
[previous review](test-suite-review.md) describe its historical scope.

## Evidence retained

The previous review's first failures, later passes, deliberate settings skips,
and separate red diagnostic remain unchanged. Its archive is in the main
repository at `.night-evidence/overnight-2026-11-06/partial-tests/evidence/`.
The sibling `manifest.json` maps the former
`/home/hsa/projects/list_app-night-tests/.night-evidence` root to that location.
Archived drivers are not replayed.

New private logs are in `.verification-evidence/` in the `browser-verify`
workspace. Preserve these logs before workspace cleanup.

## Confirmed test defects

The two historical due-day failures reproduced under UTC before the test
repair (`timezone-before.log`). Both tests used host-local date construction
although the grouping rule uses Europe/Oslo before setup.

Only the two test files were restored from `night-1-tests-partial`. The actual
diff was inspected. Fixed UTC instants retain explicit expected dates and
cover default-zone midnight, configured-zone midnight, confirmed instants,
and clock remounts. All 20 affected tests pass under UTC and Europe/Oslo
(`timezone-after-utc.log`, `timezone-after-oslo.log`). Product code is unchanged
in this separate change.

## Sign-in interruption

The historical controlled diagnostic was restored from `vywxvymk`, not merged
with its old ancestry. Before any product repair it failed at the intended
assertion (`signin-before.log`): no login request, an interrupted-sign-in alert,
no write authorization, and the password prompt still visible.

This confirms the controlled clear-hint/identity-epoch mechanism. It does not
prove the cause of every archived browser failure. Product repair and fresh
review are pending.

A fresh full UTC frontend run passed 1,115 tests and failed only this added
diagnostic (`frontend-before-repair.json`). A six-case real-browser check of
the historical engine-specific nodes passed unchanged in 13.42 seconds
(`browser-focused-before.log` and XML). No retry was added. These passing
browser observations do not replace the archived first failures.

The failed final WebKit admin case was matched from XML to port 43337 and
`browser-final-temp/popen-gw0/test_admin_sign_in_rooms_creat1/member-trace.zip`.
Its network trace has session GET 401, login POST 200, then session DELETE 204.
The earlier zero-POST schedule is therefore not the only observed stage.
Network timing alone does not identify the JavaScript continuation that
cancelled sign-in. Parsed request metadata is retained in
`archived-final-signin-network.json`.

The controlled test now covers both precheck and in-flight login schedules.
Both fail at their intended final assertions before repair
(`signin-two-stages-before.log`). The explicit-sign-out negative test was
strengthened to require an empty view and a durable signed-out snapshot state;
it passes before repair (`real-signout-negative-before.log`).

## Rejected changes after reload

The archived WebKit first failure is retained. The rejection appears before
reload and disappears afterward. Passing reruns do not erase this result.

Source inspection found separate durable writes: queue-entry removal and
later insertion of the Not saved record. The last queue removal can delete
the room record before the rejection is stored. An immediate reload can
therefore find neither record. A deterministic regression and atomic-settle
repair are in progress in the isolated `browser-verify-rejection` workspace.
The archived failed profile has no IndexedDB export, so its exact storage
state at unload is not proven.

## Private execution boundary

An actual runtime audit found child directories at mode 775 and files at 664,
despite a healthy runtime-doctor report. Both children were interrupted before
further work. The owner approved repair of only their verified owned paths:
seven roots and 105 entries, without symlinks or shared-parent changes.
Protected before/after records are `runtime-permission-*.json`.

The same peer session was then restarted with inherited umask 0077 and a
private mode-700 TMPDIR. A fresh no-tools canary passed. Actual new runtime,
session and artifact paths were audited as 700/600 before source access.
Old paused children were not discoverable under the new TMPDIR (`Async run
not found`). Their state and evidence remain intact. Bounded fallback children
use the private root and wait for an allocation audit before source reads.
This changed no global harness setting or product behavior.

## Verification still required

- Fail-before and pass-after evidence for each product repair.
- Fresh independent review of actual diffs and evidence.
- Affected frontend checks and full three-engine browser verification.
- All 120 deliberate reminder-settings skips unchanged.
- No Android run, release-gate change, shared-line move, or deployment.
