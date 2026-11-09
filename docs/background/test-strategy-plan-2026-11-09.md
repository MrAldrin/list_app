# Test strategy: bounded next steps — 9 November 2026

Lifecycle: tracked. Planning result for **lr-4rc**, not implementation or acceptance.

## Recommendation

**Reduce how often broad tests run before spending more time making them faster.**
Finish the approved tier/selection tools, then the approved gate documentation.
Keep the four three-engine smokes, full Python/frontend checks and affected
checks at deploy. Run broad browser feedback nightly and after shared-code
changes; the owner has accepted that some findings arrive after deploy.
Do not promise a three-minute full suite. Keep browser concurrency at **four**.
Try only one cheap lower-layer transfer before approving a wider cleanup.

Current Beads decisions supersede the older handoff: **lr-gt2.1 is approved**;
**lr-gt2.6 is implemented**, not accepted. **lr-005.1.7** approves conditional
removal; **lr-005.1.8** approves the new deploy gate. Do not reopen those choices.
The pre-approved **lr-005.1.5/6** may proceed within their recorded limits.
No acceptance, deployment, source merge or scheduler is authorized here.

## Established evidence, not a new baseline

| Exact tree/configuration | Reusable result | Meaning and limit |
| --- | --- | --- |
| `integration` `ltoqrxzw/6d4b0dcb` | Inventory: 1,792 Python, 1,114 frontend, 606 browser cases; 2 declared Android bodies | Python attempt: 1,783 pass/9 build-dependent skips, 53.84 s. UTC frontend: 1,112 pass/**2 fail**. Archived browser: 484 pass/**2 fail**/120 intentional skips, 662.37 s. Android unmeasured. |
| Published repairs `lr-1nn`, `runtykqu/c3483bc3` | Python 1,792 pass; frontend 1,128 pass in UTC and Oslo; browser 486 pass/120 skips, 620.79 s | Review-ready, not accepted. Causal sign-in/queue repairs and timezone tests are not on integration. Historical first failures remain evidence. |
| Local combined checkpoint `slworksn/37fa7e55`, `-n 4` | Three clean samples: 541.12, 532.55, 529.66 s; each 490 pass/120 skips | Median **532.55 s**; fallback on this tree only. Repeats 2–3 have no swap-out and about 5.4–5.8 GiB available. Unpublished helper/reliability work; do not import it silently. |
| Same checkpoint, `-n 6` / `-n 8` | Six: two clean 373.99/377.79 s, then **failed** 398.73 s. Eight: one clean 339.19 s | Six is not a stable series. Eight has about 0.72 GiB minimum available and positive run-local swap-in/out deltas. Neither is a safe default; no evidence for 10/12. |
| Matrix `lr-gt2.6`, `vwozlzup/db369199`, integration-based, `-n 4` | Collection 202/202/202 → 202/163/163; one run 408 pass/120 skips, 515.41 s; two reviews PASS | Exactly 39 detailed bodies retain Chromium and lose 78 Firefox/WebKit copies. Timed-due stays three-engine. This is **not** the combined checkpoint and not a comparable speed measurement or stability proof. |

Times above are reported test/command elapsed, not end-to-end setup cost.
Builds/installations can be outside them. Inventory group costs are aggregate
**worker-seconds**, not elapsed savings; Vitest file spans overlap. Old helper-only
557.65 s and joint 372.07 s all-attempt median are superseded candidates, not
clean combined-tree measurements. The latter includes a teardown error.

**Experiments that changed a decision:** toast overlays explained long item
clicks; sign-in/create/close helpers were small. Queued feedback was a valid
contract, so readiness checks retained `Added` assertions instead of changing
the product. Waiting for writes/logout before navigation retained error filters.
Run-local memory measurements rejected eight workers on the combined tree.
**Experiments that did not resolve a cause:** isolated green reruns and two
old-tree loaded runs did not explain timed-due Save. Its failed trace/body was
recycled; passing `item.edit` bodies cannot replace it. The six-worker Home-row
failure has retained artifacts but no diagnosis. A low SwapFree value or a
boot-total counter does not prove active pressure; engine RSS is not attribution.

## Apply the five ranked research methods

| Research rank/method | Fit here; already done; decision |
| --- | --- |
| 1. Broad journeys, detail lower down | Strong fit, but pure rule tests already exist. Mounted UI assembly is often missing. Transfer one small body, not a wholesale rewrite. Simulated IndexedDB cannot replace native storage/offline journeys. |
| 2. Smaller engine matrix | Already approved and implemented in lr-gt2.6. Preserve its exact opt-ins and timed-due exception; do not propose or count those cuts again. The research's full-matrix-before-release rule does **not** fit the owner's newer deploy decision. |
| 3. Remove/merge with assertion maps; stronger-model challenge | Audit has 13 candidates and **zero eligible now**. Use an independent map reviewer under lr-005.1.7. A stronger model is useful for missing-assertion checks, not proof of equivalent fault detection or a reason for another broad audit. |
| 4. Measure first | Inventory, traces and repeated checkpoint samples already answer the large baseline questions. Measure only a selected tool/transfer or inspect the retained failure. Do not rerun a baseline to learn the repo. |
| 5. Affected-test selection | Best immediate feedback lever with cadence. Static imports miss routes, SQL, shared stores and selectors. Use a transparent standard-library map with full fallback; no new impact-analysis dependency or coverage-percentage gate. |

## Three prioritized checks/decisions — future execution only

### 1. Deliver tier/selection tools; then make cadence explicit

**Benefit: high; confidence: high for fewer broad runs, unknown for selected time.**
Candidate: observed `integration=ltoqrxzw/6d4b0dcb`, with **no copied unaccepted
matrix/helper code**; record a new base ID if integration later changes.
In lr-005.1.5 use a small tier wrapper and registered layer/smoke markers:
Python, frontend, four-body three-engine smoke, explicit affected Chromium, full.
Full means Python + frontend + all current browser cases (`-n 4`), including
the matrix if later accepted; Android remains a separate relevant-device run.
Never remove cases through default marker filters.
Use the exact four smoke bodies in the cadence input. Do not weaken gates.

Narrow lr-005.1.6 to a **print-only** standard-library selector. Use the selection
map, `jj diff --from <base> --to @` (default `integration`), resolve/log both IDs,
union explicit rules and validate paths. Unknown/new/deleted/renamed paths,
shared auth/sync/schema/worker/config/helpers, invalid diff or empty rule matches
select full. An empty diff means no changes, not a pass. Keep engine-independent
nodes; a simple `-k chromium` is not proof of complete affected coverage.
Keep new selector unit checks in an explicit, separately reported self-test
entry point, so the owner's existing-suite count invariant remains literal.
Do not delete or skip existing tests to offset new tests. If that cannot meet
both requirements, stop and record the conflict rather than waive the proof.

**Smallest check:** static/synthetic cases from the map (script, local UI,
reminder, shared code, mixed/test/prose/unknown/new/delete/rename/invalid/empty),
then before/after exact node-set equality and one locked Chromium validation
per bead. Smoke collection must be four bodies × three engines. Retain required
AGENTS.md checks and frontend lint; these do not authorize extra baselines.
**Outcomes:** correct inclusion/reasons → useful optional feedback tool; any
miss or unexplained count difference → stop, keep full/manual selection.
Selected feedback does not certify the full candidate.
**Budget/stop:** each existing bead ≤3 h, ≤40k new model tokens, at most one
browser execution unless its recorded fixture-change requirement applies;
count collection is separate. Stop on first unclear failure, proof conflict or
budget exhaustion. No retry to obtain green. Suggested worker: Sol low; review
as recorded. Keep .5/.6 writes separate: tier script/browser guide versus selector
script/testing guide; no selector markers/config changes. Both use own workspaces.

Then lr-005.1.8 reconciles the guides and deploy script's actual checks, using
real command names. The map's full fallback schedules broad **feedback**; it
must not silently restore a full-browser deploy gate. For an unknown path,
retain all affected candidates plus smoke rather than claim no coverage.
New deferred **lr-005.1.9** adds an explicit full-tier result receipt
and failure handoff after owner approval; no hidden scheduler. Until then the
night-run operator owns the manual full run and records a failure bead.

### 2. Pilot one lower-layer transfer, not thirteen deletions

**Benefit: small immediate (~6 gross worker-s), potentially medium if reusable;
confidence: medium; verification cost: medium.** Use lr-005.1.7 on its actual
baseline after .5, and begin with audit row 3 below. A mounted RoomLists check
must cover the fixed-day, ready-store assembly, not just `dueTally` again.

| Remove/merge shortlist | Retained proof required; action now |
| --- | --- |
| `test_svelte_due_center.py::test_room_card_counts_what_is_due_in_the_list` | Tomorrow's milk → `1 due` beside Groceries, no `overdue`; retain tally tests and add mounted RoomLists proof. Pilot first; keep browser until reviewed. |
| `test_svelte_tags.py::test_tap_filters_the_items` | Chip pressed state, milk-only then bread/milk and order; existing filter rules lack click→render assembly. Next only if pilot is cheap. |
| `test_svelte_items.py::test_add_trims_python_whitespace` | Exact U+0085 submit → normalized callback, `Added Oat Milk`, sole row; existing normalize/API tests lack AddItem→ListView assembly. About 2 gross worker-s: do not build a large harness for this. |
| Merge `test_reload_shows_no_due_toast` into grouping smoke; merge suggestion ranking/scroll into keyboard journey | **KEEP.** Real reload/no-toast and viewport/wrap/focus assertions are missing from the proposed targets. Audit rows 11–13 need owner choice; recommend no cuts. |

**Smallest check:** add only that mounted card case; compare every old assertion
and input with the retained tests; obtain independent map agreement; run the
focused frontend file and old Chromium node once, then affected retained checks
if removed. Record replacement cost and explicit count delta; required quality
checks still apply. **Outcomes:** full map plus cheap fixture → remove only that
body under the existing rule; missing assembly, red checks or expensive fixture
→ keep it and stop. No protected-case deletion or change to the smoke set.
**Budget/stop:** ≤90 min within .7's 3 h ceiling, ≤25k new model tokens; ≤35 min
on fixture feasibility, ≤2 focused browser executions, no new full baseline.
Sol high worker and the bead's independent reviewer; stop without deletion if
review disagrees or any assertion has no retained home. Do not expand to row 2
or 1 in the same pilot. Subtract replacement time; never add matrix savings again.

### 3. Gate any concurrency work on the retained failure

**Potential benefit: ~30% on the old combined tree; confidence: low; check cost: low.**
This is a hypothesis from the two clean six-worker samples, not an accepted gain.
No proposed default increase. New deferred **lr-005.1.10** reads only
`combined-n6-r3` logs/traces/server logs for
`test_both_offline_add_the_same_tag_to_an_item_once[chromium]`, matched to
`slworksn/37fa7e55`, not the standalone matrix. Distinguish a sign-in response,
server start, wrong room state or missing artifact; compare the event order with
the helper contract. This does not authorize test/browser execution.
**Outcomes:** concrete mechanism → propose one separately approved causal check;
ambiguous/missing evidence → keep four workers, no new series. Even a diagnosed
failure does not prove six-worker stability or permit a WebKit-specific cap.
**Budget/stop:** 30 min, zero test/browser runs, ≤12k new model tokens, Sol low;
stop at one classified mechanism or explicit uncertainty. No profiler, artifact
recovery claim, repair or code publication. Timed-due stays in **lr-gt2.4**;
only a retained failed Save body can justify its separate repair.

## Retained protection and non-goals

Keep all four three-engine smokes. Keep real SW/CacheStorage/update, IndexedDB
snapshot/reconnect/revocation, offline conflicts/multidevice, Unicode engines,
keyboard/touch/focus, live cancellation and stale-write journeys per the matrix.
Unique wiring may run once; native storage/offline/input/engine assertions do
not become redundant because a reducer has tests. Retain native date/reload
coverage, intentional P2 settings skips and Android's separate relevance rules;
Android time and real Safari-device behavior remain unknown.

Do not repeat n=4 checkpoint samples, old-tree Save chase suites, n=6 series,
n=8/10/12 tuning, helper micro-optimization, pass-trace removal, shared-server
fixtures, the approved matrix audit or a generic stronger-model cleanup.
No new dependencies, product edits, skips/retries/longer waits, settings
reactivation, backlog/plan edits, integration/main moves or deploys in lr-4rc.
One heavy suite at a time; every browser command, including collection, uses
`flock /home/hsa/.local/state/night-loop/list_app/browser.lock`.

## Evidence homes and handoff

Read a feature-local report without merging it:
`jj file show -r <bookmark> docs/background/<file>`.

| Bead/bookmark | Change / report |
| --- | --- |
| lr-gt2.5 | `oyuqnmvu/5c591be7` · `test-suite-reduction-methods.md` (ranked sources) |
| lr-005.1.1 | `psqyoumn/d534316e` · `test-inventory-2026-11-09.md` |
| lr-005.1.2 | `mprklvpl/25bc1ac4` · `test-selection-map-2026-11-09.md` |
| lr-005.1.3 | `yzkwxqql/f50394fa` · `test-removal-candidates-2026-11-09.md` (complete 13 maps/costs) |
| lr-005.1.4 | `qvrqvrkz/aaa8f419` · `test-run-cadence-2026-11-09.md` (exact smoke commands) |
| lr-gt2.6 | `vwozlzup/db369199` · `engine-matrix-implementation-2026-11-09.md` (collection and reviews) |
| lr-gt2-checkpoint | `slworksn/37fa7e55` · `browser-suite-speed-2026-11-08.md`, `engine-matrix-review-2026-11-08.md`, `combined-review-2026-11-08.md` |

Final speed receipt/handoff/manifest: private archive
`/home/hsa/projects/list_app/.night-evidence/browser-speed-2026-11-08/`.
Receipt overrides historical claims/workspaces; latest Beads overrides its old
model/matrix status. Repairs remain at **lr-1nn**; parent **lr-005/lr-gt2** stays
unfinished. Existing .5/.6/.7/.8 own implementation: do not create duplicate queues.
New deferred tasks require owner approval; existing recorded approvals stand.

Planning used verified **openai/gpt-6.1-sol:xhigh**, not the obsolete Opus choice.
Runtime doctor and fresh synthetic no-tools Luna xhigh canary passed. One bounded
Luna xhigh reader extracted audit/inventory facts; this was **not independent
review**. Review: **NONE**, as configured. No tests, browser, profile, build or
implementation ran. Only this report and private task records changed. Static
reference, whitespace and one-file-scope checks are recorded in lr-4rc.
