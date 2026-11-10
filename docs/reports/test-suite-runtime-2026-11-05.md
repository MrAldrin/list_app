# Test runtime results — 5 November 2026

This report summarizes the overnight test-suite review. It measures suite
runtimes and selected test groups. It is not function-level profiling or a
statement of today's test status.

> **Result at closeout: partial. Full verification was blocked.**
> The test-only repair passed its checks, but the final browser run failed.
> The partial candidate (`oqpnzkyx`) was superseded by lr-1nn and removed from visible history on 2026-11-10.
> This report does not accept that candidate or approve a product fix.

## Total time

These are elapsed command times, including command startup. Dependency setup
and frontend builds are separate. Runs did not overlap.

| Suite | Workers | Baseline | Final candidate | Outcome |
| --- | ---: | ---: | ---: | --- |
| Python | 8 | 60.70 s | 49.69 s | Baseline: 1,783 passed, nine skipped because the frontend build was absent. Final: 1,792 passed, no skips. |
| Frontend, UTC | Vitest-managed | 8.89 s | 8.48 s | Baseline: 1,112 passed, two failed. Final: 1,115 passed. |
| Frontend, Europe/Oslo | Vitest-managed | Not measured | 8.30 s | Final: 1,115 passed. |
| Chromium, Firefox, and WebKit | 4 | 662.37 s (11 min 2 s) | 622.47 s (10 min 22 s) | Baseline: 484 passed, two failed. Final: 485 passed, one failed. Each run had 120 intentional skips and no teardown errors. |
| Android emulator | — | Not measured | Not measured | Inventory only; no emulator run. |

**These numbers do not show a speed improvement.** There is only one full
baseline and one final sample per comparable command. The Python runs cover
different built-route checks; the frontend candidate adds one test; the browser
runs have different failures. No runtime optimization was implemented.

## What was expensive, and why keep it?

The Python and browser costs below are **summed testcase worker-seconds**, not
elapsed group times. Parallel tests overlap. Removing a group would not save
its summed worker time from the total runtime. The frontend file span also
can overlap other files.

| Group | Layer | Observed cost | Value and protection | Review conclusion |
| --- | --- | ---: | --- | --- |
| Due center, 48 cases | Three browser engines | 359.71 worker-s | Important: due grouping, bell navigation, reveal, and live UI updates | Keep; cost alone does not justify removal. |
| Item operations, 30 cases | Three browser engines | 269.09 worker-s | Critical: real UI add, edit, delete, and undo paths | Keep. |
| Offline reconnect, 30 cases | Three browser engines | 161.38 worker-s | Critical: saved views, network recovery, and access revocation | Keep. |
| API idempotency, 224 cases | Python | 59.31 worker-s | Critical: repeated requests must not duplicate writes or cross room boundaries | Keep real transactions and password-hashing cost. |
| Sign-in rate limits, 13 cases | Python | 34.48 worker-s | Critical: per-room and all-room sign-in limits | Keep production-cost password checks. |
| Offline integration, 59 cases | Frontend | 6.44 s file span | Critical: stored queues, sign-out guards, replay, and conflicts | Keep. |

For the final browser run, rounded phase totals were 292.98 setup,
1,778.06 test-action, and 382.81 teardown **worker-seconds**. These phases overlap
across workers; they are not a breakdown of its 622.47 s command elapsed time.
Teardown includes diagnostics and cleanup.

## Findings

### Two timezone assumptions in tests were repaired

Two frontend assertions used host-local dates near midnight while the app's
default grouping zone was Europe/Oslo. The partial candidate uses fixed instants
and checks the actual default-zone midnight boundary, clock remounts, and
confirmed due instants. It does not change product behavior.

The affected 20 tests passed in UTC and Europe/Oslo. Three temporary faults
were caught at the intended assertions: use the wall date instead of the
confirmed instant, use the wrong default zone, or omit the clock's initial
check. Product files were then restored and the tests passed again.

### Sign-in interruption remained unresolved

The final failed case was
`test_admin_sign_in_rooms_create_and_reset[webkit]`. Its visible alert said
**Room sign-in was interrupted by sign-out**. The baseline also showed that
symptom in Firefox, so it was not WebKit-only.

Isolated and grouped reruns passed, but they do not erase the full-run failures.
A separate intentionally failing diagnostic reproduced a feasible saved-data
clear/identity-epoch race in a controlled UI test. It failed at the intended
assertion in three UTC runs and one Europe/Oslo run. This establishes a possible
mechanism, not the exact cause of the real-browser failures. It remains outside
the candidate, on `vywxvymk`; no product repair was included.

### A rejected change disappeared after reload in one WebKit run

The baseline showed the rejection message before reload but not afterward.
Reruns and the final run passed. A persistence or lifecycle cause was not
established. The first failed trace was retained; no wait or retry was added
to hide the failure.

## Measurement and review limits

- Machine: AMD Ryzen 7 5700X, 16 logical CPUs, about 15 GiB RAM, Linux.
- Fresh workspace dependencies used existing package caches and installed
  Playwright browsers. This was not a cold-machine benchmark.
- Separate setup times: `uv sync` 0.31 s, `npm ci` 3.28 s, first frontend build
  2.92 s. Final frontend build: 2.73 s.
- Browser engines: Chromium 153.0.8010.12, Firefox 155.0, WebKit 26.6.
  Baseline and browser jobs used UTC; frontend candidate checks also used Oslo.
- Baseline: `qmqznusu`. Test repair: `npnxozpl`. Candidate closeout: `oqpnzkyx`.
- Selected permissions/revocation, deletion/restore, snapshot clearing, and
  offline synchronization/conflict tests received deep review. Other areas
  received an inventory, not a complete assertion audit.
- The 120 reminder-settings skips were deliberate until S3. No scenario,
  assertion matrix, engine, device, retry rule, timeout, or release gate changed.
- Independent review confirmed the scope and evidence limits. Its final verdict
  was **BLOCK**, because the required browser gate was still red.

## Conclusion and sources

The review found clear test defects and unresolved app symptoms. It did not
justify deleting slow coverage or claim that all assertions were reviewed.
Investigate the sign-in and rejected-change findings before claiming full
verification. Repeat comparable measurements before claiming a speed gain.
The [backlog](../../plans/backlog.md) owns follow-up work and approval.

The detailed [test review evidence](../background/test-suite-review.md) is the
canonical technical record, including exact commands, exits, traces, and review
results. [Earlier speed measurements](../background/test-suite-speed.md) cover
an older suite and are not a direct comparison. Both records remain in the
repository; the local site replaces their links with an exclusions notice.
This page presents the reader-facing summary without exposing internal logs,
agent/session records, or the rest of `docs/background/`.

For current commands and execution rules, use the [testing guide](../testing.md).
