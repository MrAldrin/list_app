# Test-suite review evidence

## Run and ownership

This is the evidence record for the [test review brief](../../plans/test-suite-review.md).
The review started on 2026-11-05. It is bounded, not an audit of every assertion.
**Outcome: partial; full verification is incomplete.** The test-only repair is
reviewed and green. The final browser gate still fails on sign-in interruption.
No product repair or acceptance is included.

- Conductor: `01a1ad92-275c-776a-8cbd-cb97c67da161`, OpenAI Sol 6.1/high.
- Entry workspace: `night-tests`, `/home/hsa/projects/list_app-night-tests`.
  Lead-created and Lead-managed. Base: `qmqznusu` / `fa387556`.
- Child workspace: `night-tests-offline`,
  `/home/hsa/projects/list_app-night-tests-offline`, change `npnxozpl`.
  Created and managed by this Conductor. Test-only writer; no graph authority.
- Read-only inventory run: `9b5b5f4f-3e7d-4cb6-836b-cfa7ac14cd16`.
- Offline test worker run: `88464f31-a685-4338-a063-299498181c84`.
  Both first attempts request Luna/xhigh. Effective settings are checked at launch.
- Sign-in diagnostic worker: `f144504a-0cae-467a-b701-2142de6b206a`,
  requested Luna/xhigh. Child workspace `night-tests-signin`,
  `/home/hsa/projects/list_app-night-tests-signin`, change `vywxvymk`,
  is Conductor-created and managed. Any failing diagnostic stays outside the
  passing candidate's ancestry.
- Baseline job: owned Zellij pane 45, tab 16. Commands run one at a time.
  Logs, machine-readable results and browser artifacts: `.night-evidence/`
  in the entry workspace. This ignored folder must be preserved before cleanup.

## Baseline conditions

- Linux x86-64, kernel `7.0.0-42-generic`, AMD Ryzen 7 5700X,
  16 logical CPUs, about 15 GiB RAM.
- Node `24.15.0`, npm `11.12.1`, Playwright `1.63.0`.
  Runtime browser versions: Chromium `153.0.8010.12`, Firefox `155.0`, WebKit
  `26.6` (`browser-versions.txt`). UTC for baseline/browser jobs; frontend
  candidate checks also use Europe/Oslo.
- Fresh workspace dependencies: `uv sync`, then `npm ci` in `frontend/`.
  Existing package caches and installed Playwright binaries were reused. This
  is not a machine-cold benchmark. Setup/build time is separate from tests.
- Default Python workers: eight. Browser workers: four, all three engines.
- No Android execution. No competing full-suite jobs within this delivery.
- Initial disk headroom: about 16 GiB. Pause heavy work below 6 GiB free.
- No speed improvement is claimed from a single before/after sample.

## Baseline outcomes

The bounded implementation, checks, and independent review are complete.
Full verification is incomplete because the final browser gate failed.
The accepted P2 work is not reimplemented or reactivated. Its
[validation record](reminders-p2-validation.md) owns earlier outcomes.

All commands below use `TZ=UTC`. Elapsed times include command startup, but not
previous dependency setup. The Python baseline ran before the frontend build.

| Command | Exit | Outcome | Elapsed |
| --- | ---: | --- | ---: |
| `uv sync` | 0 | Fresh workspace Python environment | 0.31 s |
| `cd frontend && npm ci` | 0 | Fresh workspace Node dependencies | 3.28 s |
| `uv run pytest -q --durations=20 --junitxml=.night-evidence/python-baseline.xml --basetemp=.night-evidence/python-baseline-temp` | 0 | 1,783 passed; nine skipped because the real frontend build was absent | 60.70 s; pytest 59.38 s |
| `cd frontend && npm test -- --reporter=json --outputFile=../.night-evidence/frontend-baseline.json` | 1 | 1,112 passed; two failed | 8.89 s |
| `cd frontend && npm run build` | 0 | Build completed | 2.92 s |

The frontend failures are in `due-reminders.test.ts`:

- `localDay` → “writes the local day as YYYY-MM-DD”.
- `confirmed timed deadlines` → “uses the confirmed instant day rather than
  the wall date at device midnight”.

Both tests construct host-local dates near midnight but use rules whose default
zone is Europe/Oslo. The documented contract is
[Europe/Oslo before setup](../due-date-reminders.md#what-counts-as-due), not the
host's zone. Test repairs must keep explicit expected dates and verify both UTC
and Europe/Oslo execution. They must not repeat the product calculation.
The earlier offline queue-date defect is already repaired in this base and
passed this run. It is not changed again.

## Earlier WebKit failures: evidence and hypothesis

The Lead supplied four exact P2 failed node IDs, all under WebKit:

- `test_svelte_admin.py::test_admin_sign_in_rooms_create_and_reset`
- `test_svelte_install_browser.py::test_manifest_follows_the_page`
- `test_svelte_room_switcher.py::test_switching_to_a_room_without_access_asks_for_its_password`
- `test_svelte_rooms.py::test_logout_shows_the_prompt_before_the_server_answers_and_retries`

Read-only inspection of the archived `browser-full.log` shows the same app
alert in all four: **Room sign-in was interrupted by sign-out.** This is not
only a locator timeout. The room-switcher case also has a cancelled-session
request teardown error. Earlier three serial reruns passed; those passes do
not make the first run clean.

The manifest case's `phone-trace.zip` and `server.log` show an initial session
GET returning 401. The test fills the password and presses Enter, but no login
POST appears. The trace records the second navigation at monotonic 70426 ms,
the session GET at 70529 ms, and Enter at 70564 ms. These timestamps locate the
sequence; they do not identify when every JavaScript continuation completed.

A possible cause is an initialization/access-clear race with the identity epoch
captured by `RoomHandle.login()`. `signInRoom()` can cancel before its login
POST if that epoch changes during async snapshot work. The separate diagnostic
below proves this mechanism under a controlled schedule, **not that it caused
the archived browser failures**. No product defect is repaired. Do not add a
helper delay to hide it. Product changes require a Bucket B decision.

Archive source, left unchanged:
`/home/hsa/projects/reminders-archive/p2-closeout-2026-11-05/checks/`.
Current runs and any diagnostic reproduction are recorded separately below.

## Risk-led review map

The read-only inventory deep-read selected cases in these areas, not every
file listed below. Broader test-layer counts are static inventory only.

| Behavior | Risk | Existing evidence inspected or mapped | Weakness and action |
| --- | --- | --- | --- |
| Room/share permissions and revocation | Unauthorized edits or room metadata disclosure | `test_api_room.py`, `test_api_share.py`, `test_api_invitations.py`; frontend share/revocation cases; browser share, room-management, reconnect, and access-gone cases | Reviewed cases check real rejection, unchanged data, and privacy boundaries. No specific extra permission assertion justified by this bounded review. |
| Saved data, deletion, and restore | Lost restored fields or stale deleted data | API room deletion and item restore; change tracking/pruning; snapshot clearing and multi-device tests | Share restore checks only name, but uses the same handler already checked for full fields by room restore tests. No duplicate share-only field test added. |
| Offline queues, reconnects, and conflicts | Lost/duplicate writes or writes without consent | API conflicts/idempotency/changes; frontend rebase and persisted rejection cases; browser offline conflicts/reconnect/multi-device cases | Two browser negative-send checks use fixed 300/500 ms waits. Replacing these with API-idle observation alone would not prove no later automatic send. Deferred rather than claim a reliability fix without causal evidence. |
| Due-day and confirmed-instant grouping | Incorrect day group near midnight | Frontend `due-reminders.test.ts`, product rules, and due-date contract | Two tests confuse host-local construction with configured-zone grouping. Repair fixed test instants and retain explicit default/configured-zone boundary assertions. |
| Core list UI journeys | Broken browser wiring | Existing list/item/share/browser files mapped; full suite execution | Inventory and execution only, not full assertion review. |
| Android install/recovery | Device-specific install or remembered-access failure | `android_tests/test_android_chrome.py`: two source tests | Inventory only. No emulator or benchmark; scenario/tier choices remain owner decisions. |

Static inventory: 74 Python test files with 1,001 declared test functions;
54 Vitest files with 549 lexical test blocks; 37 browser test files with
180 declared functions; one Android file with two tests. Parameterized and
engine-expanded collected counts differ. These source counts are not a
coverage score.

### Intentional settings skips

The 120 browser skips are 40 parameter-expanded scenarios × three engines:
34 in `test_svelte_private_reminders.py` (102 engine-expanded skips), and six
in `test_svelte_policy_editor.py` (18). Every reason names P2 and re-enabling
in S3. The private-reminders public-share visitor test remains active in all
three engines. No settings skip or entry point changed.

### Review limits

Selected permission/revocation, deletion/restore, snapshot clearing, and
sync/conflict tests received deep reading. Broader UI/presentation, all Android
assertions, and much of the remaining suite received inventory only. No claim
is made that all assertions, security paths, engines, or device states were
audited. Runtime collection is not an assertion review.

## Test-only improvements and deliberate-fault checks

Child `npnxozpl` changes only `due-reminders.test.ts` and
`due-clock.svelte.test.ts`. Fixed UTC instants replace host-local date
constructors. Assertions now check the actual default-zone midnight crossing,
including before remount. Configured-zone and confirmed-instant checks remain.
The existing explicit Kiritimati/Adak checks and queue-retention tests remain.
One direct default-zone test is added; no scenario is removed.

The Conductor ran the child checks sequentially after the browser baseline.
Scoped Prettier formatting exited 0. The two files passed all 20 tests under
both `TZ=UTC` and `TZ=Europe/Oslo`, before and after the temporary faults.
Each targeted run took 1.40–1.64 s including npm startup.

Fault driver: `.night-evidence/check_timezone.py`. In the disposable child,
it saved original product bytes, applied one fault, ran the selected test,
and restored the original bytes in `finally`. The final child diff contains
only the two test files.

| Deliberate fault | Selected test (`npm test -- <two files> -t ...`) | Result |
| --- | --- | --- |
| Group a confirmed deadline using its wall date instead of its confirmed instant | `uses the confirmed instant day rather than` | Exit 1: expected `tomorrow`, received `today`. |
| Use UTC as the default day-grouping zone | `uses the pre-setup Europe/Oslo zone` | Exit 1: expected Jan 6, received Jan 5. |
| Omit the immediate clock check at mount | `checks the day at once` | Exit 1: expected Nov 5, received Nov 4 after remount. |

All faults were caught by the intended assertion. Filtered-out tests in these
fault probes are not new source skips. Restored runs passed 20/20 in both zones.
Logs: `mutation-*.log`, `timezone-target-*.log`, `timezone-restored-*.log` and
`timezone-results.jsonl` under `.night-evidence/`.

## Current browser baseline and reruns

`TZ=UTC uv run pytest browser_tests -q -n 4 --durations=30
--junitxml=.night-evidence/browser-baseline.xml
--basetemp=.night-evidence/browser-baseline-temp` exited **1**:
484 passed, two failed, 120 intentional skips, no teardown errors.
Pytest elapsed 662.01 s; command elapsed 662.37 s. Dependency setup and the
2.92 s frontend build were separate. Browser artifacts record disposable data.

The two first failures are:

- `test_svelte_accessibility.py::test_every_control_has_a_name[firefox]`:
  the same sign-in-interrupted alert as the earlier WebKit failures. The
  symptom is therefore **not WebKit-only**.
- `test_svelte_offline_conflicts.py::test_refused_tick_is_listed_and_save_mine_anyway_applies[webkit]`:
  the rejected-change message appears before reload but is absent afterward.
  The page still shows the other device's notes. Persistence, lifecycle, and
  harness timing causes remain to be distinguished; this is not called a
  harmless flake.

First-run logs, XML, screenshots and traces remain in
`.night-evidence/browser-baseline*`. The following unchanged-code reruns passed,
with no teardown errors. They do not replace the two first failures.

| Rerun | Workers | Outcome | Command elapsed / pytest elapsed |
| --- | ---: | --- | ---: |
| Current Firefox sign-in failure alone | 0 | 1 passed; exit 0 | 8.68 / 8.41 s |
| Current WebKit rejected-change failure alone | 0 | 1 passed; exit 0 | 4.59 / 4.35 s |
| Prior four WebKit sign-in cases plus current Firefox case | 0 | 5 passed; exit 0 | 23.05 / 22.80 s |
| Same five sign-in cases plus current WebKit conflict case | 4 | 6 passed; exit 0 | 13.56 / 13.31 s |

Exact commands and temp directories are in `browser-rerun-results.jsonl` and
`.night-evidence/rerun_browser.py`. Logs/XML/artifacts use the corresponding
`browser-isolated-*` and `browser-signin-*` names. Serial logs identify Firefox
155.0 and WebKit 26.6. No added retry, skip, timeout, or helper wait was used.
These runs establish intermittent outcomes, not a cause or a flake rate.

The failed WebKit conflict trace shows the rejected operation request at
monotonic 17576 ms and reload at 17591 ms, shortly after the first rejection
message appears. A persistence-versus-reload race is possible, but trace timing
does not prove that IndexedDB failed or identify the precise storage step.
No automatic re-send appears in the post-reload network trace. Investigate
persistence separately; do not replace the reload with a delay and call it fixed.

## Runtime versus value

The table uses baseline observations, not proposed savings. Python/browser group
costs are **aggregate testcase worker-seconds**, including their reported test
phases. They are not group wall times and cannot be subtracted from suite elapsed
time. Vitest file span is from its JSON start/end timestamps and can overlap
other files. The initial Python suite is not comparable with a built final run
because nine build-dependent cases skipped.

| Test or group | Layer/engine | Measured cost | Value | Unique protection | Reliability | Action |
| --- | --- | ---: | --- | --- | --- | --- |
| API idempotency, 224 cases | Python, eight workers | 59.31 worker-s | Critical: duplicate writes can corrupt user state | Stored response replay, op-ID reuse, cross-room boundaries | Baseline passed | Keep real transactions and hashing; no reduction proposed. |
| Sign-in rate limits, 13 cases | Python, eight workers | 34.48 worker-s | Critical: unauthorized access and lockout boundaries | Per-room/all-room limits with real password checks | Baseline passed | Keep production-cost hashing. |
| Offline integration, 59 cases | Vitest | 6.44 s file span | Critical: queued data and consent | Durable queues, sign-out guards, replay and conflicts | Baseline passed | Keep; earlier queue-date defect is already repaired. |
| Due center, 48 cases | Three browser engines, four workers | 359.71 worker-s | Important: users need correct due views | Bell grouping, navigation, reveal and live UI wiring | Baseline passed | Keep; cost alone does not justify removal. |
| Items, 30 cases | Three browser engines, four workers | 269.09 worker-s | Critical: core saved-list edits | Real UI add/edit/delete/undo paths | Baseline passed | Keep. |
| Offline reconnect, 30 cases | Three browser engines, four workers | 161.38 worker-s | Critical: saved views must clear or recover correctly | Real engine storage/network/revocation wiring | Baseline passed | Keep. |
| Rejected tick and explicit retry | WebKit | 23.37 testcase-s including failed wait | Critical: rejected user edits must remain visible | Rejection survives reload; retry needs user action | First failure; isolated/group reruns passed | Preserve evidence; investigate persistence/lifecycle, no delay-based fix. |
| Control names | Firefox | 12.30 testcase-s including sign-in timeout | Important: controls must be usable with assistive tools | Real rendered control names | First failure before its main assertions; reruns passed | Treat as sign-in symptom, not accessibility proof for that failed case. |
| Android journeys | Dedicated emulator | Unmeasured | Important: install and standalone behavior differs | Chrome/install/remembered-access/network-recovery journey | Inventory only | Keep serial; no benchmark or scenario change approved. |

There is one full frontend baseline sample: 8.89 s with two failed tests.
The integrated candidate passes 1,115 tests in 8.48 s under UTC and 8.30 s
under Europe/Oslo. It adds one test. These are functional checks, not enough
samples for a speed claim. No speed improvement, median, or repeatability
claim is made. Existing speed work is not repeated as an optimization project.

## Decisions and remaining work

| Item | Evidence and expected benefit | Protection that must remain | Recommendation |
| --- | --- | --- | --- |
| Bucket B: product sign-in interruption | Prior/current browser failures show the same app alert; controlled diagnostic reproduces a feasible clear-hint/epoch schedule | New sign-out/401 transitions must still block obsolete sign-ins | Approve a separate small product task. Use the diagnostic to test a fix, then establish its connection to real-engine failures; do not add a helper wait. |
| Bucket B: rejected change lost after reload | One WebKit first failure; short time between rejection display and reload; reruns passed | Durable rejection record and explicit retry consent | Investigate persistence/lifecycle before any product repair. Keep the failing trace and existing assertion. |
| Existing Android scenario/tier decisions | No emulator benchmark performed; device-specific costs unknown | Installation, standalone access, and safe emulator cleanup | Keep current scenarios and serial execution until the owner decides the open items in the speed plan. |

The two fixed-wait negative browser checks noted in the risk map remain possible
Bucket A follow-up work, not a recommendation to weaken their observation.
No scenario, assertion matrix, engine, device, release gate, dependency, or
production setting changed in this batch.

## Integrated candidate checks

The reviewed test change is the parent of this documentation change. The
combined checks run in the entry workspace, not only in the child. No Python
files changed, so Python quality checks are read-only; no auto-fix was needed.
The frontend build exists before the final Python run.

| Check | Exit | Outcome | Command elapsed |
| --- | ---: | --- | ---: |
| `cd frontend && npm run lint` | 0 | Prettier and ESLint passed | 10.86 s |
| `cd frontend && npm run check` | 0 | Type and Svelte checks passed | 4.76 s |
| `TZ=UTC npm test -- --reporter=json --outputFile=../.night-evidence/frontend-final-utc.json` in `frontend/` | 0 | 1,115 passed; no failed or pending tests | 8.48 s |
| Same command with `TZ=Europe/Oslo` and `frontend-final-oslo.json` | 0 | 1,115 passed; no failed or pending tests | 8.30 s |
| `cd frontend && npm run build` | 0 | Build passed | 2.73 s |
| `uv run python scripts/build_docs_site.py` | 0 | 51 Zensical source-page warnings; wrapper validated 37 exclusion redirects and 2,807 generated local links | 1.76 s |
| `uv run ruff format --check .` | 0 | Passed | 0.10 s |
| `uv run ruff check .` | 0 | Passed | 0.04 s |
| `uv run ty check` | 0 | Passed | 0.19 s |
| `TZ=UTC uv run pytest -q --durations=20 --junitxml=.night-evidence/python-final.xml --basetemp=.night-evidence/python-final-temp` | 0 | 1,792 passed; no skips; pytest 49.10 s | 49.69 s |
| `TZ=UTC uv run pytest browser_tests -q -n 4 --durations=0 --junitxml=.night-evidence/browser-final.xml --basetemp=.night-evidence/browser-final-temp` | **1** | **485 passed, one failed, 120 skipped; no teardown errors**; pytest 622.21 s | 622.47 s |

Exact command/exit/timing records: `.night-evidence/final-results.jsonl`.
The local-only docs build has separate `docs-build.log`, `docs-build.exit`, and
`docs-build-time.txt`; no server was started or owner preview replaced.
Full frontend JSON is also saved as `*.pretty.json` to let file-reading review
tools read the aggregate results without the original single-line size limit.

The final failed node is
`browser_tests/test_svelte_admin.py::test_admin_sign_in_rooms_create_and_reset[webkit]`.
Its app alert is again **Room sign-in was interrupted by sign-out**. This case
passed in the earlier serial and parallel groups, then failed in the full final
run. No extra rerun substitutes for this red final gate. The current Firefox
accessibility and WebKit conflict cases passed in this final run, but their
first failures remain part of the outcome.

The full browser baseline took 662.37 s and the final command took 622.47 s.
They each have one sample, different failures, and unchanged browser/product
code. This is runtime variation, not a measured optimization. Final
`--durations=0` phase sums are approximately 292.98 setup, 1,778.06 call, and
382.81 teardown **worker-seconds** (rounded per report), not wall-time phases.
They include diagnostics/cleanup and overlap across workers. The overall
622.21 s pytest time is the elapsed figure.

## Separate failing sign-in diagnostic

The diagnostic is **not in the candidate ancestry**. It is a single new
`frontend/src/lib/data/index-signin-race.test.ts` on change
`vywxvymkluqkqxyrrkswqqxrrquxlokn`, commit
`d2c6a988b5cc4f4b1c00b79eade03f9c2f4be1bf`, based on `qmqznusu`.

It mounts the real `PageShell` and password form, with the real snapshot store
backed by `fake-indexeddb` and controlled promises. An initial session 401 shows the form
while its asynchronous saved-data clear is pending. The test submits through
the visible form, then lets that clear's hint advance the identity epoch during
sign-in's precheck. It awaits the public login result and requires successful
login, write authorization, no alert, and ready state. A non-throwing event
source preserves the success path.

This is a feasible mechanism-level schedule. It is not a real-engine/HTTP
reproduction or proof of the archived failures' exact cause. The fake API
records **zero `api.login` calls**, the public login result is unsuccessful,
write authorization stays false, and the visible alert says sign-in was
interrupted. All four runs fail at this intended final assertion, not a timeout:

- Three `TZ=UTC npm test -- src/lib/data/index-signin-race.test.ts` runs:
  exit **1** each; command elapsed 2.27, 1.96, and 1.93 s.
- One identical Europe/Oslo run: exit **1**; 1.91 s.
- `npm run check` in the diagnostic child: exit 0. Scoped Prettier: exit 0.

Logs and exact exits: `.night-evidence/diagnostic-results.jsonl` and
`diagnostic-{utc-1,utc-2,utc-3,oslo}.log`. The actual side-change diff is
`signin-diagnostic.diff`. The diagnostic driver exited 0 because it expected
red tests; **the individual test commands exited 1**. No product code changed.

To reproduce later, create a disposable workspace at the diagnostic revision,
install its existing frontend dependencies with `npm ci`, then run the command
above in `frontend/`. The historical driver records the original child path;
that path has been removed. Do not import this failing change into the main
candidate without the separately approved product fix.

## Independent review and closeout

Fresh Luna/xhigh reviewer `e1dbfb1e-2f09-4e6d-960b-8037a60ad056` inspected
`qmqznusu..npnxozpl` through the actual range diff, source contracts, product
hash comparison, and deliberate-fault/restoration logs. **Code review: PASS,
no actionable findings.** It did not run tests. Its early evidence limitation
on the large baseline JSON was resolved by providing formatted originals for
final review. Effective reviewer settings were verified by the parent through
run status, even though the reviewer's restricted tools could not show them.

The second fresh reviewer is `61ae7255-cbbe-4136-aee7-fd42c4c75896`,
Luna/xhigh as verified by the parent. It found a stale child diff artifact and
an insufficient diagnostic success check. The parent refreshed the child
snapshot/diff, retained the non-throwing fake event source, awaited the public
login result, and added write-authorization checks. Resume
`56bf744f-6da8-483e-895e-ce3498a34125` passed the revised static diagnostic
review. Final resume `e71ebd08-29d0-4ab9-aee4-8f8adf59b8dd` reviewed the
combined six-file diff, testing guide, evidence, and executed diagnostic.
It confirmed the scope and claim limits. **Final verdict: BLOCK**, because the
required browser gate remains red; this is a partial result, not accepted code.
It also requested two stale report-status sentences be corrected. Those
closeout corrections are applied here. The code-review pass above is not a
full-verification pass.
The stale desk-plan status finding was sent to the Lead; the Lead confirmed
it will update desk-owned records after graph handback. Feature plan copies
are deliberately unchanged.

### Results and workspace disposition

| Order | Result | Change ID |
| --- | --- | --- |
| 1 | Timezone-stable default/configured due-day tests and real midnight clock checks | `npnxozplnlvpqqnumntmyxzrktlosnsl` |
| 2 | Testing guide, hub link, corrected browser runtime guidance, and this evidence | `oqpnzkyxtwqwvuwkwnrysvtzqwqzytou` |
| Separate only | Intentionally failing sign-in diagnostic, outside the two-change line | `vywxvymkluqkqxyrrkswqqxrrquxlokn` |

Both Conductor-created child workspaces were forgotten and removed after their
writers finished, checks ran, and artifacts were preserved. The test repair is
reachable from the entry line; the diagnostic remains a separate nonempty jj
head. No other workspace, bookmark, or parked line changed. Owned job panes
45–49 are closed. No owned server or test job remains. The entry workspace and
interactive Conductor remain Lead-managed; they are not removed here.

Retained generated evidence is about **1.4 GiB**, with about 15 GiB free disk.
Preserve the entry workspace's ignored `.night-evidence/` before removing that
workspace. It holds first/final failed traces, passed rerun evidence, XML/JSON,
raw logs, exact exit records, mutation/diagnostic drivers, actual diffs, and
review copies under `reviews/`. The earlier archive is unchanged. Historical
drivers record original working directories; replay needs a disposable workspace
at the stated revision, not the removed child path.

**Next action:** owner/Lead review of this partial result and the separate
Bucket B product investigations. Full verification remains incomplete because
the final browser gate is red. No push, deploy, acceptance, coverage removal,
settings activation, or Android execution is authorized by this report.
