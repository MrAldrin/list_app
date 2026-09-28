# Test suite speed and device coverage

## Goal and scope

Keep useful regression coverage while shortening the development loop. Desktop browser benchmarking and small, verifiable optimizations are authorized; Android scenario removal or consolidation still requires owner approval. Python optimization is lower priority because the default suite is already relatively fast.

## Measured baseline

Local measurements on the current main-staging-based working copy:

| Command | Result | Runtime |
| --- | --- | --- |
| `uv run pytest -q --durations=20` | 346 passed | 9.22s |
| `uv run pytest browser_tests -q -n 0 --durations=15` | 50 passed | 285.73s |
| `uv run pytest browser_tests -q -n 2 --durations=15` | 50 passed | 147.62s |

Two workers reduced desktop browser runtime by about 48% in the initial comparison. Android was not running and was not benchmarked.

Sequential follow-up runs on the same machine (2026-09-28; 50 desktop browser cases each; pytest-reported time):

| Workers | Runs | Outcomes | Runtime |
| --- | --- | --- | --- |
| 2 | 3 | 50 passed plus one teardown error; then 50 passed; then 50 passed | 147.93s, 147.97s, 148.12s |
| 4 | 2 | 50 passed plus one teardown error in each run | 89.47s, 83.09s |

The two-worker runs were consistently ~148s, but one reported a Firefox Service Worker installation error during teardown of the restart scenario. One four-worker run timed out taking a Chromium teardown screenshot (30s); the other reported the same Firefox Service Worker installation error. All test bodies passed, but runs with teardown errors **do not count as clean passes**. Four workers used roughly 332–361% CPU versus 166–167% at two workers (from `/usr/bin/time -v`); its per-process maximum RSS is not a total-memory measurement. No benchmarks overlapped. The provisional two-worker recommendation was **retracted**: ~148s remains too slow and one repeat failed in teardown; four workers did not finish cleanly in either run. Desktop documentation retains the serial `-n 0` command pending profiling and reliable improvements; Android also remains `-n 0`. Investigate teardown flakiness before recommending either parallel setting. A subsequent serial profiling run is recorded below.

Serial profiling run (2026-09-28; `uv run pytest browser_tests -q -n 0 --durations=0`): **50 passed in 282.23s**. Summing pytest's 50 per-case phase durations (rounded to hundredths): setup **38.80s** (0.78s/case), call/test actions **221.34s** (4.43s/case), teardown **22.00s** (0.44s/case); ~0.09s is rounding/report overhead. The full suite ran at ~78% CPU according to `/usr/bin/time -v`. The test-action phase accounts for ~78% of wall time, so server/fixture setup alone cannot deliver a substantial reduction. `call` includes browser operations and one test's in-body server restart; `teardown` includes screenshots and trace archiving as well as closing contexts and servers. Individual substeps were not timed in that run; do not attribute their costs without measurement. This serial run had no teardown errors. Exploratory inspection of its 92 trace archives (46 scenarios create two contexts; four scenarios do not use `sessions`) shows 526 `Frame.click` calls totaling ~111s and 546 `Frame.expect` calls totaling ~64s; these trace timings include some setup/teardown and may overlap, so they are **not** additive shares of the 221s call phase. They suggest repeated UI interactions deserve focused measurement before trying server or artifact optimizations. Read-only harness review recommends exception-safe timers for repeated UI setup helpers and the in-test restart, followed by server spawn/readiness and per-context artifact/cleanup costs; keep all assertions, diagnostics, and isolation unchanged. A screenshot or trace failure can currently interrupt subsequent cleanup and error assertions (`browser_tests/conftest.py`), so any cleanup refactor needs separate, focused validation rather than being slipped into profiling.

Follow-up action timing (2026-09-28): a disposable pytest plugin outside the repository wrapped the existing test helpers and `TestServer.restart` with `perf_counter` timers in `try/finally`, without changing test bodies or assertions. A targeted serial Chromium run of restart plus the 12 stale-deletion action cases passed (13 passed, 37 deselected, 78.01s); its call phase was 63.82s, including 23.71s in `create_list`, 20.43s in `share_link`, 7.46s in `delete_list`, and 0.52s in the single restart. The subsequent serial full run (`uv run pytest browser_tests -q -n 0 -p speed_probe --durations=0`, with the temporary plugin on `PYTHONPATH`) **passed all 50 cases in 281.84s**. Measured call-phase time was 220.45s:

| Timed region | Calls | Inclusive total | Mean per call |
| --- | ---: | ---: | ---: |
| `create_list` (room navigation, login, list creation, assertions) | 44 | 87.38s | 1.99s |
| `share_link` (menu, dialog, link read, close, assertions) | 50 | 55.82s | 1.12s |
| `delete_list` | 24 | 17.48s | 0.73s |
| `reset_link` | 8 | 6.29s | 0.79s |
| `add_item` | 48 | 5.27s | 0.11s |
| `prepare_action` | 28 | 5.05s | 0.18s |
| In-test `server.restart()` | 2 | 1.19s | 0.60s |

These non-nested helper regions total ~178.47s, leaving ~41.98s in other test-body actions and assertions (including theme cases). The helper durations include **both** real browser interactions and expectation waits; they do not isolate individual clicks, navigation, or assertion polling. The earlier trace inspection suggests interactions and expectations both matter, but its trace totals cannot be added to these timings. Restart is small in this profile; optimizing it first is unlikely to reduce suite time substantially. Repeated login/create and share setup dominate measured call time, but any replacement with seeded prerequisites must preserve dedicated end-to-end journeys and all security checks. Next, split the costly helper paths into UI action versus expectation/navigation timing before selecting a single optimization; keep the timing probe outside the delivered code. These are single-run observations, not an established speedup.

The one-case seeding experiment (2026-09-28): for the stale room `add` case only, a temporary code change inserted the prerequisite list directly into that case's disposable SQLite database, then kept real browser login, item addition, list deletion, stale WebSocket Add, and the existing authorization/persistence assertions. The targeted Chromium and Firefox cases passed (2 passed, 26 deselected, 10.29s); their call phases were **2.56s and 3.80s**, respectively. The corresponding unmodified cases in the preceding full-suite profiling run took **4.45s and 4.93s**. These are single observations from different run shapes, not repeatable full-suite savings; direct seeding also couples browser tests to the database schema and bypasses list creation and share-dialog coverage in the changed case. The temporary one-off code was **reverted** before the shared implementation below. That first experiment did not change the then-delivered browser tests. Broader seeding still required mapping retained UI journeys and authorization checks; saving ~1–2s in one case was not proof of a many-times-faster suite. No edge-case scenarios were dropped.

Implemented follow-up (2026-09-28): seed only the disposable list and random share token for all **28 deleted-list cases** (24 stale-action variants and four room-deletion navigation cases). Each case still starts a fresh server/database and two independent browser contexts, logs the room member in through the UI, adds the item through the UI, opens the appropriate real room/public page, deletes the list/room through the UI, sends the delayed stale action, and retains every rejection/persistence assertion. Public-sharing cases still exercise real browser list creation, the Share dialog, token reset and room-access boundaries; no scenario or browser engine was removed. See `browser_tests/test_deleted_lists.py` and [browser testing](../docs/browser-testing.md).

Eight targeted cases passed in **35.68s**. The full serial Chromium/Firefox suite (`uv run pytest browser_tests -q -n 0 --durations=0`) passed **50 cases in 238.22s**, versus the preceding serial profiling run's 281.84s: **43.62s (~15.5%) faster** in this single comparison. Summed pytest phases were setup 38.75s, call 177.21s, teardown 22.22s; compared with 38.82s, 220.49s, 22.45s in the preceding instrumented baseline. Deleted-list call time fell from 130.79s to 87.18s (~43.61s), while other call time was 89.70s versus 90.03s. Different runs have natural variation and the baseline used a small disposable timing plugin, so this is evidence of a substantial local improvement, not a repeatability claim or a production benchmark. Required Ruff format/lint and default pytest checks passed (346 fast tests; existing Starlette/httpx warnings). Recommend **keeping** this scoped change: the saved time is material and authorization/write assertions are preserved; the trade-off is that deleted-list cases now depend on schema columns and no longer check the list-creation or Share-dialog UI themselves. Those UI journeys remain tested separately. Do not silently seed the public-sharing journeys or remove rare edge cases without a separate coverage review.

Sequential repeat benchmarks of the seeded full serial suite (2026-09-28; same command, three additional runs, no overlap):

| Run | Result | Pytest time | Setup | Call | Teardown | Deleted-list calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Initial seeded run | 50 passed | 238.22s | 38.75s | 177.21s | 22.22s | 87.18s |
| Repeat 1 | 50 passed | 237.55s | 38.67s | 176.41s | 22.39s | 85.53s |
| Repeat 2 | 50 passed | 237.67s | 38.75s | 176.53s | 22.30s | 85.93s |
| Repeat 3 | 50 passed | 238.59s | 38.65s | 177.62s | 22.23s | 87.17s |

All four seeded runs finished cleanly within **237.55–238.59s**; three repeats alone average ~237.94s. The earlier unseeded instrumented run was 281.84s (50 passed, 220.49s call, 130.79s deleted-list calls), and another uninstrumented serial profile took 282.23s. This supports a roughly **44-second / 16% reduction** on this machine, concentrated in deleted-list call time, not merely random run-to-run fluctuation. Because we did not rerun the unseeded suite in the same benchmark series, avoid claiming a controlled A/B or hardware-independent speedup. `time` measured ~85–86% CPU across repeats; its 733–774 MB maximum RSS is per-process, not aggregate browser/server memory. No failures or teardown errors appeared in these repeats. Remaining call time is ~176–178s: ~86–87s in deletion cases and ~90–91s elsewhere. Next possible improvement is a **coverage review of the 24 stale-action room/public × Chromium/Firefox permutations**: compare each assertion against unit/service coverage and preserve real browser cases for unique WebSocket/revocation and navigation behavior before proposing any removals. This has more potential than revisiting restart (~1.2s per full suite), but requires owner agreement before dropping a scenario. Do not assume parallel workers are reliable based on serial repeat stability.

## Verified desktop parallelism (2026-09-28)

On the current seeded suite, two fresh serial baseline runs passed all 50 cases in
238.46s and 239.08s; two unmodified two-worker runs passed in 124.46s and
124.36s. Two unmodified four-worker runs each failed in teardown (50 test bodies
passed): Chromium screenshot timed out in the revoked-room-rename test, and
Firefox reported Service Worker installation failure around server restart.
A targeted four-worker run repeated the screenshot failure in four of five
attempts. A temporary per-page progress log identified the *member's revoked
room page* as the failing screenshot. Browser-error timestamps put the Firefox
error during/just after the deliberate server outage. Merely waiting for Service
Worker readiness did not fix it; adding promise catches in app code and
unregistering workers also failed in trial runs. Those experiments were reverted.

Two scoped changes were retained: after the revoked member navigates to the
password-protected room, assert that the password prompt has rendered before
screenshot teardown; before restarting the server, navigate the member and
visitor's existing pages to `about:blank`, retaining their independent browser
contexts, cookies, localStorage and Service Worker registrations. On return,
assert remembered room access, revoked old link, and active Service Workers that
can update. This avoids leaving live pages trying to load scripts during the
intentional outage. No browser cases, security assertions, screenshots on pass,
or trace archives were removed; server/browser errors still fail tests. The
fixture now attempts every screenshot, both trace archives and both context
closures even when a screenshot fails, reporting diagnostic failures. An injected
screenshot exception produced a failing teardown while retaining both traces
and the visitor screenshot. The live-page-across-restart behavior is not tested:
the restart scenario verifies browser storage and registration persistence across
navigation, not live reconnection. This is a testing-scope trade-off, not proof
that live pages survive a server restart.

Fourteen consecutive full four-worker runs with the final navigation fix passed
all 50 cases: 71.21, 71.82, 70.50, 71.55, 71.58, 72.57, 71.43, 71.50,
75.10, 73.29, 73.00, 73.38, 73.34 and 73.30s. The last six also assert
successful Service Worker updates after restart; the first eight predate that
additional assertion. An additional final serial run passed in 241.05s; three
post-fix two-worker runs passed in 124.69, 124.96 and 124.91s. The last six
four-worker runs average 73.57s,
versus the initial fresh serial pair's 238.77s (~69% lower wall time), though
the final serial run with added assertions took 241.05s. Four workers consumed
roughly 367–386% aggregate job CPU in measured final runs versus 85% serial;
`time` maximum RSS is per process, not system-wide memory. Recommend explicit
`-n 4` for desktop on this machine, `-n 0` when debugging, and retain Android
at `-n 0`. Repeatability across machines/CI and longer-term flake rates remain
unverified. See [browser testing](../docs/browser-testing.md) for the run command.

### Follow-up: open-page recovery (2026-09-28)

A new test keeps a room member's list tab open through a real server-process
restart. A document marker confirmed in both engines that NiceGUI automatically
reloads this tab. Without navigating/reloading it from the test, a separate
visitor context opens its public link and adds an item; the recovered member tab
must display the new item and the database must persist it. Both Chromium and Firefox
passed in a targeted serial run (2 passed) and six targeted four-worker runs
(2 passed each). Nine consecutive full four-worker runs passed **52 cases** in
74.83s, 75.16s, 75.39s, 75.41s, 77.73s, 75.26s, 75.36s, 77.25s and 76.01s,
with no teardown errors. The last three include an assertion that the tab's
original document was replaced by an automatic reload. The existing
storage/Service Worker restart scenario still leaves its pages before restart;
this separate test restores explicit open-page recovery coverage without
removing any existing assertion. It proves recovery of this room page on this
machine, not reload-free live reconnection or every browser/network interruption. Keep the four-worker desktop recommendation; Android
remains serial. Longer-term and other-machine reliability are still unknown.

## Important distinction: browser workers versus Android workers

The measured parallelism improvement applies to **desktop Playwright tests**, not Android. Those browser tests already exist on this branch; no offline-branch integration is required to try more workers.

The current Android harness operates one shared emulator via `adb -e`, changes its connectivity, and manipulates Chrome and home-screen icons. Running it with multiple pytest workers would cause interference. Keep Android at `-n 0`. True Android parallelism would require separate emulators, explicit serial targeting, and isolated forwarding/device state per worker. That is extra complexity and resource use, not an initial optimization.

## Priority 1 — Decide coverage and test tiers

Before implementing Android simplifications, agree which scenarios belong on the current baseline:

- **Already present:** `android_tests/test_android_chrome.py` contains a password-prompt smoke check and an installation/standalone-login/remembered-access/network-recovery journey.
- **Historical only:** the offline experiment adds installed cold launch, saved offline contents, reconnect refresh, and revocation/deletion clearing. Do not import these tests into a branch without the corresponding feature. Review their lessons when the new offline frontend is implemented, rather than restoring the discarded implementation. See [offline findings](../docs/offline-findings.md).
- **Proposed baseline:** retain a small installation/standalone/remembered-access Android journey. Decide whether the separate password-prompt smoke test earns its overlap through faster diagnostics. Review the recovery assertion separately: it proves reload after an outage, not automatic recovery or offline availability.
- Retain comprehensive authorization and data-integrity coverage in Python/browser layers. Before removing device permutations, map each assertion to retained coverage and identify any genuinely device-specific interaction being lost.

Proposed execution tiers:

1. During editing: affected Python tests; targeted Chromium cases for UI changes.
2. Task completion: full Python suite, preserving the repository's required Python quality checks.
3. Relevant integration changes and releases: full desktop browser suite across Chromium and Firefox.
4. Installation, storage, lifecycle, or network changes, plus applicable releases: Android checks and appropriate iPhone acceptance.

The current serial desktop browser command is documented in `docs/browser-testing.md`. Update Android guidance and broader execution-tier guidance only after the corresponding coverage/tier decisions are approved. Keep the default Python command free of browser/device requirements.

## Priority 2 — Desktop browser parallelism and overhead

Small, independently verifiable experiments:

1. Repeated serial/two-/four-worker full suites on the same machine; failures and measured runtimes are recorded above.
2. Four desktop workers are now recommended on the tested machine; keep a serial debugging command and do not change Android or the global worker setting.
3. Measure setup, test body, and teardown costs separately. Each case currently creates a fresh server/database and repeats UI setup; browsers themselves are already session-scoped.
4. Benchmark saving screenshots and trace archives only on failure. Preserve useful failure diagnostics and browser/server error assertions. Recording traces still costs time even if successful archives are discarded; benchmark reduced recording separately.
5. Seed routine prerequisites or reuse isolated authentication setup where appropriate, while keeping dedicated end-to-end login/create/share tests. Preserve fresh database and browser-session isolation; do not share mutable server state merely to save startup time.
6. Use targeted Chromium runs during iteration rather than removing Firefox coverage from integration checks. Review the large stale-action matrix for layer-appropriate coverage, without dropping distinct handler/security checks blindly.

Acceptance: unchanged behavioral assertions, all selected cases pass, repeatable runtime improvement, no cross-test contamination, and useful artifacts on deliberate failure.

## Priority 3 — Simplify and measure Android checks

Depends on the coverage decisions in Priority 1. No offline-feature tests are imported by default.

1. Time server startup, installation, native UI inspection, launcher lookup, browser assertions, and cleanup separately on the dedicated emulator.
2. Keep an already-booted emulator available during relevant work; distinguish emulator startup time from test execution. Benchmark snapshot-based startup only if it preserves a known device state.
3. Use Chrome's Playwright/CDP connection for web content and event-driven waits; reserve Android accessibility-tree dumps for native installation menus and launcher interactions.
4. Keep the dedicated emulator free of stale disposable icons using narrowly scoped, safe cleanup. Never clear unrelated Chrome data or shortcuts. Reduce repeated launcher searches without bypassing the actual icon-launch assertion.
5. Avoid repeating installation and cold-launch journeys for every business-rule variant. Keep representative device-specific lifecycle checks and put broad rule permutations in browser/Python tests, after mapping retained coverage.
6. Replace avoidable fixed sleeps with observable readiness conditions where reliable. Do not blindly shorten timeouts: successful condition waits already finish early. Historical Chrome persistence delays require evidence before removal.
7. Keep Android serial. Consider multiple isolated emulators only if the reduced suite is still a measured bottleneck and the additional maintenance/resource cost is justified.

Acceptance: deterministic repeated passes, intact installation/lifecycle assertions, restored connectivity and port mappings after failure, and a documented runtime comparison. Continue to use disposable servers/data only.

## Priority 4 — Python fixture efficiency

The default suite is already about nine seconds, so optimize after the expensive layers.

- Remove unnecessary valid-hash creation immediately overwritten by invalid hashes in `tests/test_password_hashes.py`; preserve invalid-hash rejection and admin-repair coverage.
- Look for reusable immutable production-cost hashes in other setup paths, never shared mutable database state.
- Profile subprocess startup and worker scheduling before further changes.
- Preserve the existing [production-cost hashing decision](test-speed-experiments.md). Cheaper or hybrid hashing would require an explicit reconsideration, not a silent optimization.
- Run all required Ruff and pytest checks after Python changes; compare runtime and coverage rather than only test counts.

## iPhone relevance and remaining acceptance

Android tests can expose shared application bugs in authorization, saved-data handling, and reconnection flows. They cannot establish iPhone correctness: Safari/WebKit, installed-app storage, installation, and background/cold-launch behavior differ from Android Chrome.

Because primary users are on iPhone, prioritize a short real-iPhone acceptance checklist for critical installed-app journeys, especially early in future offline work. Linux Playwright WebKit can add useful engine-level coverage but is not installed iOS Safari; evaluate a small subset rather than multiplying every browser test automatically. Do not make Android the main evidence for iPhone readiness. See [installation acceptance](../docs/home-screen-installation.md#outstanding-real-device-acceptance-checklist) and the [future frontend plan](offline-frontend-migration.md).

## Progress

- [x] Reviewed current browser/Android harnesses and historical offline Android tests, including later experiment changes.
- [x] Measured current Python suite and serial/two-worker desktop browser suites; all passed.
- [x] Recorded proposed priorities and browser-versus-Android parallelism distinction.
- [ ] Owner approves baseline Android coverage and execution tiers.
- [x] Repeat two-worker browser runs and benchmark four workers; record timings, resource observations, and teardown errors above.
- [x] Retract provisional two-worker desktop command after owner feedback; keep desktop and Android serial while profiling.
- [x] Profile per-case pytest phases in a clean serial full-suite run; test actions dominate (see above).
- [x] Measure repeated UI setup helpers and in-test restart in targeted and full serial runs; create/share setup dominates the timed call phase (see above).
- [ ] Split helper time into browser interactions, navigation and expectation waits; measure teardown substeps (screenshot, trace archiving, context close) separately before changing diagnostics.
- [x] Investigate browser teardown errors and retain scoped fixes; fourteen 50-case runs and nine additional 52-case full four-worker runs passed. Other-machine and longer-term reliability remain unverified.
- [x] Add a dedicated open-page restart recovery test for both browser engines; targeted and nine full parallel runs passed.
- [x] Try seeding one stale-deletion prerequisite in isolation; both browser cases passed and became modestly faster, but revert the one-off change pending a coverage/suite-level approach.
- [x] Seed prerequisites for 28 repetitive deleted-list cases; targeted and full desktop suites pass; one full run improved ~44s versus the preceding baseline (see above).
- [x] Repeat the seeded full serial suite three times sequentially; all 50 passed in ~238s with no teardown errors (see above).
- [ ] Map stale-action browser permutations to existing service/security tests before proposing any case removal; measure and verify further desktop browser optimizations in small chunks.
- [ ] Benchmark and simplify approved Android scenarios; Android remains unmeasured.
- [ ] Agree lightweight iPhone-focused acceptance and optional WebKit coverage.
- [ ] Optimize Python setup after higher-impact work.
- [x] Update the browser testing guide with measured desktop commands and limits; Android guidance remains serial.
