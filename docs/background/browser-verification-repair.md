# Browser verification repair

## Status

The bounded repairs are verified and ready for acceptance review under local
task `lr-1nn`. No result is accepted or deployed. The current task record carries approval for bounded product
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
prove the cause of every archived browser failure. The bounded repair is
implemented. Independent code review and the full browser gate pass.

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

The controlled test covers both precheck and in-flight login schedules.
Both failed at their intended final assertions before repair
(`signin-two-stages-before.log`). The final schedule releases the durable clear
but delays its notification across the precheck or request, so the new durable
barrier cannot deadlock the test. In that revised schedule the original
precheck still fails, while the old in-flight case can pass because its hint
is already stale (`signin-revised-schedule-before.log`). The original two-stage
red result remains retained, not replaced.

The repair adds an optional opaque origin to local clear notifications. The
origin is never stored or broadcast. Only the initiating handle ignores its
own already-applied echo. Other handles and tabs still process revocations.
Sign-in captures the original identity epoch, then awaits its own durable
clear before reading the sign-in baseline. A failed or throwing clear blocks
sign-in. Newer external clears and real sign-outs still cancel the attempt.
A pending-clear heuristic that could swallow an external revocation was
rejected.

The durable-barrier test fails against the original `index.ts` at the intended
precheck assertion (`signin-barrier-before.log`). Product bytes were restored
and hash-checked afterward. The explicit-sign-out negative test was strengthened
to require an empty view and a durable signed-out snapshot state; it passed
before repair (`real-signout-negative-before.log`). All nine new sign-in cases
and the affected existing tests pass after repair (`signin-after-safety.log`).

The owner clarified room-switch scope: preserve the existing release/session
retention behavior. Switching rooms does not revoke the old room's cookie.
Tests instead require active-room isolation, with and without a real sign-out;
a late old-room login cannot change the new room's state, and real sign-out
still prevents old-room authorization or saved-data restoration.

## Rejected changes after reload

The archived WebKit first failure is retained. The rejection appears before
reload and disappears afterward. Passing reruns do not erase this result.

Source inspection found separate durable writes: queue-entry removal and
later insertion of the Not saved record. The last queue removal can delete
the room record before the rejection is stored. An immediate reload can
therefore find neither record. A deterministic regression reproduced that hole
for a server rejection and a permanent HTTP failure. Both failed at the intended
record-preservation assertion, not a timeout (`rejection-worker/fail-before-repair.log`).
The archived failed profile has no IndexedDB export, so its exact storage
state at unload is not proven.

The repair removes the queued operation and inserts its Not saved row in one
IndexedDB transaction. The queue serializes this transition with its other
storage writes. The visible Not saved row is admitted only after the write
finishes. Reopening storage then finds the rejection and no queued operation.
Tests retain unknown rows, reject duplicate rejection keys, and cover memory
fallback. The worker's 180 affected tests and type check pass; raw logs are
copied under `rejection-worker/`.

An aborted transaction leaves the previous queue record, rather than a committed
empty gap. This does not add an automatic new-operation retry or replace the
browser reload assertion with a delay. Existing retry/update/dismiss behavior
is unchanged.

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

## Joint candidate and checks

The owner approved an additive merge for joint verification, not acceptance.
Owner room-switch scope is also recorded in closed local decision `lr-vcn`.
No source line, child workspace revision, shared desk change, `integration`,
or `main` was rebased or moved.

| Result | Change / initial commit |
| --- | --- |
| Timezone-only test repair | `mtxnyrxx` / `2861709f` |
| Sign-in repair and safety tests | `uzoooqwn` / `a1eea56d` |
| Atomic rejected-change settlement | `spmlowno` / `71f58716` |
| Initial evidence record | `kwuvsykk` / `1d9b2d3b` |
| Additive joint candidate | `runtykqu` / `df72df0e` |

The child source diff was inspected before combination. The additive merge
had no conflicts. Both repair histories remain separately reachable.

| Check | Current result | Evidence |
| --- | --- | --- |
| Full frontend, UTC | 1,128 passed; no failed or pending tests | `frontend-final-utc.json` |
| Full frontend, Europe/Oslo | 1,128 passed; no failed or pending tests | `frontend-final-oslo.json` |
| Frontend lint, types and build | Passed | `frontend-final-{lint,check}.log`, `frontend-joint-build.log` |
| Python format, lint and types | Passed | `ruff-final-format.log`, `ruff-final-check.log`, `ty-final-check.log` |
| Full Python tests | 1,792 passed; no skips, failures or errors; 55.56 s | `python-final.xml` and log |
| Six historical engine-specific browser nodes | 6 passed in 12.56 s; no retry | `browser-focused-after*` |
| Full Chromium, Firefox and WebKit, four workers | 486 passed; 120 deliberate skips; no failures or teardown errors; 620.79 s | `browser-joint*`, exit 0 |
| Fresh independent actual-diff review | Code verdict OK; no remaining actionable finding | Grok/high runs `dc81c14e-9bfe-43c0-aede-89cc521dee8e`, follow-up `8787bd04-a8bd-49ce-bf1a-b8781ba9a69c` |

The fresh reviewer inspected current source and the parent-generated exact
combined diff. Its first P2 note asked for a clearer regression comment and
removal of an apparently unused waiter. The comment was corrected. The waiter
was retained and explicitly named as a legacy split-write fault hook: without
it the old insertion can beat the observer and conceal the original gap.
Follow-up review confirmed that rationale and found no remaining actionable
correction. The current strengthened test was then run against the original
four split-write product files. Both cases failed at the intended `remove
dropped ... expected [] to include` assertion, not a timeout
(`legacy-rejection-before-current-test.log`). The 59 filtered-out cases in this
fault probe are not source skips. All product bytes were restored in `finally`;
before/after hashes match exactly and match the browser-verified candidate
(`legacy-rejection-restoration.json`, `product-hashes-during-browser.json`).
Final full frontend and Python checks above ran after restoration.

The browser's 120 skips remain the original reminder-settings skips. No test
scenario, engine, retry rule, timeout, helper delay, or release gate changed.
The current full browser pass does not erase historical first failures or prove
the exact continuation/storage bytes in every archived failure. No Android
run, shared-line move, acceptance, or deployment is included. Final independent
evidence review `6516bd29-f789-4a8c-902b-cdb5c394a457` confirmed code and evidence
OK, with no actionable findings. All owned test panes are stopped and closed.
The parent and rejection workspaces remain available until acceptance; private
evidence must be preserved before their later cleanup.
