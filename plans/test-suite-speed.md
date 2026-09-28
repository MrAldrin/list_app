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

1. Repeat the two-worker full suite to check stability; benchmark four workers on the same machine. Compare runtime, failures, and resource pressure, without overlapping benchmarks.
2. Adopt the smallest reliably fast worker count in documented browser commands. Keep a serial debugging command; do not change the global worker setting for Android.
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
- [ ] Investigate browser teardown errors (Firefox Service Worker installation after restart; Chromium screenshot timeout at four workers) before considering parallelism reliable.
- [ ] Measure and verify further approved desktop browser optimizations in small chunks.
- [ ] Benchmark and simplify approved Android scenarios; Android remains unmeasured.
- [ ] Agree lightweight iPhone-focused acceptance and optional WebKit coverage.
- [ ] Optimize Python setup after higher-impact work.
- [ ] Update affected current testing guides with verified results and remaining limits.
