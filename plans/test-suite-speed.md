# Test suite speed and device coverage

## Goal and scope

Keep useful regression coverage while shortening the development loop. Desktop browser benchmarking and small, verifiable optimizations are authorized; Android scenario removal or consolidation still requires owner approval. Python optimization is lower priority because the default suite is already relatively fast.

## Resume here — remaining work

This plan is **open**. Desktop browser optimizations and the scoped Python
speed pass are complete locally ([measurements](../docs/background/test-suite-speed.md)); do not repeat them as prerequisites. The
remaining decisions and checks, in order, are:

1. **Owner decision:** agree which existing Android checks belong in the
   baseline (including whether the separate password-prompt smoke case is
   worthwhile) and when Python, desktop browser, Android and real-iPhone
   checks should run. Review each assertion before removing any scenario;
   do not add offline-specific tests to the current baseline. See
   [Priority 1](#priority-1--decide-coverage-and-test-tiers).
2. **After that decision:** benchmark the approved Android scenarios on the
   dedicated emulator, serially (`-n 0`). Separate startup, installation,
   native UI, browser actions and cleanup costs; make one scoped change at a
   time, retain device-specific behavior and safe cleanup, then repeat and
   compare clean runs. See [Priority 3](#priority-3--simplify-and-measure-android-checks)
   and [Android setup](../docs/android-emulator-testing.md).
3. **Owner/device decision:** agree a small real-iPhone acceptance subset and
   record device/browser versions and results when a phone is available.
   Decide separately whether a small Linux WebKit check adds value; it cannot
   replace iPhone testing. See [iPhone acceptance](#iphone-relevance-and-remaining-acceptance).
4. **Verification, not an optimization:** repeat the four-worker desktop suite
   on other machines or CI when available, and observe longer-term flakes.
   The ~59s local result is not a cross-machine guarantee.

No Android benchmarks or Android scenario removals, real-iPhone checks, or
other-machine browser checks have been performed for these remaining items. The
[progress checklist](#progress) below tracks completion; do not infer approval
from a proposed step.

## Important distinction: browser workers versus Android workers

The measured parallelism improvement applies to **desktop Playwright tests**, not Android. Those browser tests already exist on this branch; no offline-branch integration is required to try more workers.

The current Android harness operates one shared emulator via `adb -e`, changes its connectivity, and manipulates Chrome and home-screen icons. Running it with multiple pytest workers would cause interference. Keep Android at `-n 0`. True Android parallelism would require separate emulators, explicit serial targeting, and isolated forwarding/device state per worker. That is extra complexity and resource use, not an initial optimization.

## Priority 1 — Decide coverage and test tiers

Before implementing Android simplifications, agree which scenarios belong on the current baseline:

- **Already present:** `android_tests/test_android_chrome.py` contains a password-prompt smoke check and an installation/standalone-login/remembered-access/network-recovery journey.
- **Historical only:** the offline experiment adds installed cold launch, saved offline contents, reconnect refresh, and revocation/deletion clearing. Do not import these tests into a branch without the corresponding feature. Review their lessons when the new offline frontend is implemented, rather than restoring the discarded implementation. See [offline findings](../docs/background/offline-findings.md).
- **Proposed baseline:** retain a small installation/standalone/remembered-access Android journey. Decide whether the separate password-prompt smoke test earns its overlap through faster diagnostics. Review the recovery assertion separately: it proves reload after an outage, not automatic recovery or offline availability.
- Retain comprehensive authorization and data-integrity coverage in Python/browser layers. Before removing device permutations, map each assertion to retained coverage and identify any genuinely device-specific interaction being lost.

Proposed execution tiers:

1. During editing: affected Python tests; targeted Chromium cases for UI changes.
2. Task completion: full Python suite, preserving the repository's required Python quality checks.
3. Relevant integration changes and releases: full desktop browser suite across Chromium and Firefox.
4. Installation, storage, lifecycle, or network changes, plus applicable releases: Android checks and appropriate iPhone acceptance.

The current serial desktop browser command is documented in `docs/browser-testing.md`. Update Android guidance and broader execution-tier guidance only after the corresponding coverage/tier decisions are approved. Keep the default Python command free of browser/device requirements.

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
- Preserve the existing [production-cost hashing decision](../docs/background/test-speed.md). Cheaper or hybrid hashing would require an explicit reconsideration, not a silent optimization.
- Run all required Ruff and pytest checks after Python changes; compare runtime and coverage rather than only test counts.

## iPhone relevance and remaining acceptance

Android tests can expose shared application bugs in authorization, saved-data handling, and reconnection flows. They cannot establish iPhone correctness: Safari/WebKit, installed-app storage, installation, and background/cold-launch behavior differ from Android Chrome.

Because primary users are on iPhone, prioritize a short real-iPhone acceptance checklist for critical installed-app journeys, especially early in future offline work. Linux Playwright WebKit can add useful engine-level coverage but is not installed iOS Safari; evaluate a small subset rather than multiplying every browser test automatically. Do not make Android the main evidence for iPhone readiness. See [installation acceptance](../docs/home-screen-installation.md#real-device-acceptance-checklist) and the [future frontend plan](offline-frontend-migration.md).

## Progress

Completed steps and all measurements are in [background](../docs/background/test-suite-speed.md#completed-steps).

- [ ] Owner decides baseline Android coverage (including the password-prompt smoke case) and execution tiers; map device-specific assertions to retained coverage before removing scenarios. Do not import offline-only tests.
- [ ] After coverage approval, profile and benchmark the approved Android scenarios serially on the dedicated emulator; retain installation/lifecycle checks and safe cleanup, repeat clean runs, and record the runtime comparison. Android remains unmeasured.
- [ ] Agree a small real-iPhone acceptance subset and record versions/results on a real device; decide separately whether optional Linux WebKit coverage is useful.
- [ ] Verify four-worker desktop browser stability on other machines/CI when available and observe longer-term flakes; local runs alone are not cross-machine acceptance.
