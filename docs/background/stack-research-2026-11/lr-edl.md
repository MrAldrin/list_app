## Summary

**Supplied baseline:** `3ff346236bb3efaa01d8ec2fe923f971c4797845`.

**Inspected workspace:** `/home/hsa/projects/list_app-stack-lr-edl`. Repository citations below refer to this workspace. The supplied revision was not independently verified because commands were prohibited.

A fair trial asks: **Can the owner and agents make the same small change more safely and clearly?** It must not compare a complete Python app with a TypeScript demonstration that omits its difficult rules.

Keep SQLite, Svelte and the current API. First compare the current Python boundary with stronger Python types, generated declarations and runtime validation. Test TypeScript only if the owner separately approves it. Test Effect against plain strict TypeScript, not against unchecked JavaScript.

The proposed trial has three parts:

1. A fixed read/edit workflow with authorization, stale-edit rejection, durable retry and SSE notification.
2. Matched change and fault-diagnosis tasks.
3. A scorecard that separates correctness from convenience and cost.

**No result is measured yet.** This report specifies the experiment. It does not approve implementation, select a framework, close the bead or establish migration readiness.

## Evidence

### 1. Existing boundaries determine the trial

| Observed boundary | Decisive source | Trial consequence |
|---|---|---|
| Python/FastAPI serves a static Svelte app and JSON API from one origin. SQLite has one application instance. | [ARCHITECTURE.md:9–30](ARCHITECTURE.md#L9-L30) | Do not add React, another database, CORS or another production service to obtain a language comparison. |
| Access checking and database work share a transaction. Public links have a separate, list-limited scope. | [src/api/access.py:59–149](src/api/access.py#L59-L149); [src/database_crud.py:132–151](src/database_crud.py#L132-L151) | Valid input is not proof of permission. Test authorization against current database state. |
| Writes hold a process lock, use `BEGIN IMMEDIATE`, commit normally and roll back on exceptions. | [src/database_crud.py:40–68](src/database_crud.py#L40-L68) | A replacement needs equivalent ownership and cleanup, not merely an async function. |
| A savepoint rolls back a business rejection. The outer transaction stores its answer. Notification follows commit. | [src/api/ops.py:810–882](src/api/ops.py#L810-L882) | Test partial failure, stored rejection, commit order and replay separately. |
| Item edits preserve absent/null distinctions and accept stale edits when the wanted values are already stored. | [src/api/ops.py:654–707](src/api/ops.py#L654-L707); [tests/test_api_conflicts.py:196–248](tests/test_api_conflicts.py#L196-L248) | A generic version comparison or default-filled decoder can change behavior. |
| Request hashes use validated models, sorted compact JSON and explicit omission rules. Stored answers are replayed. | [src/api/idempotency.py:22–76](src/api/idempotency.py#L22-L76) | Test old request bodies and stored answers. Ordinary JavaScript serialization is not evidence of compatibility. |
| SSE reserves capacity, authorizes before streaming, subscribes before its first read and rechecks access. | [src/api/events.py:34–145](src/api/events.py#L34-L145) | A working streamed response is only part of the requirement. |
| The client persists the sent marker before transmission. Retryable failures keep the operation; other failures can remove it. | [frontend/src/lib/data/write-queue.ts:399–464](frontend/src/lib/data/write-queue.ts#L399-L464) | Lost or unreadable write answers need explicit unknown-outcome tests. |

The API contract describes full/delta reads, restore fallback, stream headers and revocation: [docs/api-sync.md:5–79](docs/api-sync.md#L5-L79). Item operations, retry and conflict rules are in [docs/api-lists-items.md:52–170](docs/api-lists-items.md#L52-L170).

### 2. Reuse the existing test review

The retained review already maps permissions, replay, offline conflicts, deletion and browser risks. It also states that its result was partial and unaccepted. It must not be presented as a green baseline for this trial: [docs/background/test-suite-review.md:3–26](docs/background/test-suite-review.md#L3-L26).

Its bounded review found useful protection in existing permission and synchronization cases. It retained fixed-window negative-send checks rather than replacing them with weaker assertions: [docs/background/test-suite-review.md:138–188](docs/background/test-suite-review.md#L138-L188). Its runtime/value table recommends keeping real transaction, replay and offline coverage: [docs/background/test-suite-review.md:238–277](docs/background/test-suite-review.md#L238-L277).

Reuse these source cases as the trial's starting material:

- **Stale edit and same-value exception:** `test_stale_edit_after_someone_renamed_is_rejected`, `test_edit_that_wants_the_stored_values_is_applied`; [tests/test_api_conflicts.py:196–225](tests/test_api_conflicts.py#L196-L225).
- **Applied/rejected replay and ID reuse:** [tests/test_api_idempotency.py:264–360](tests/test_api_idempotency.py#L264-L360).
- **Replay retention limit:** an ID can execute again after pruning; [tests/test_api_idempotency.py:375–404](tests/test_api_idempotency.py#L375-L404). This is not an unlimited exactly-once guarantee.
- **Stream headers, initial refusal and write notification:** [tests/test_api_events.py:166–231](tests/test_api_events.py#L166-L231).
- **Real worker and saved-view startup:** [browser_tests/test_svelte_offline.py:30–104](browser_tests/test_svelte_offline.py#L30-L104).
- **Reconnect requires validation and feed:** [browser_tests/test_svelte_offline_reconnect.py:144–196](browser_tests/test_svelte_offline_reconnect.py#L144-L196).
- **Rejected change survives reload and needs explicit retry:** [browser_tests/test_svelte_offline_conflicts.py:64–132](browser_tests/test_svelte_offline_conflicts.py#L64-L132).

These are inspected test sources, not tests run here. Reuse their behavioral assertions. Do not start another suite-wide inventory, mutation campaign, test-removal project or lint audit.

The supplied `related-tasks.json` lists `lr-347.4.3` and `lr-347.4.4` as open. Their checker counts, contract audit and lint findings are not available results. Send overlap to those tasks through the owner instead of repeating them.

### 3. The current tests are not already backend-neutral

A small adapter is necessary:

- API helpers import `main.app`, use Starlette `TestClient` and seed data through Python database helpers: [tests/api_helpers.py:1–115](tests/api_helpers.py#L1-L115).
- SSE tests drive ASGI directly and inspect Python subscription state: [tests/test_api_events.py:1–173](tests/test_api_events.py#L1-L173).
- Browser fixtures launch a Python process and reset tables directly: [browser_tests/conftest.py:21–108](browser_tests/conftest.py#L21-L108); [tests/server_launcher.py:30–89](tests/server_launcher.py#L30-L89).

**Proposal:** keep those existing tests. Add only a narrow trial adapter for a server URL, isolated fixture reset, process start/stop and streaming HTTP. Run common HTTP/browser assertions through that adapter. Keep internal transaction and cleanup checks native to each implementation where needed. Do not claim an ASGI-only test ran unchanged against Node.

Some existing browser bodies create lists, add items, toggle tags and rename lists before reaching their main assertion. Copying those bodies unchanged would expand the port. Instead, seed the same synthetic list/item through the common setup adapter and reuse only the selected journey and its assertions. Label it as a trial scenario, not as a pass of the original whole test.

### 4. Tools provide different kinds of feedback

Official sources support these distinctions:

- Type assertions disappear at compilation. They do not check received JSON: [TypeScript, Type Assertions](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#type-assertions).
- Pydantic can export model and union schemas. Its examples also show custom validation whose exported schema remains only a string: [official Pydantic JSON Schema source](https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/json_schema.md). Exporting a schema does not export arbitrary Python validation code.
- `openapi-typescript` generates **runtime-free types**: [official introduction](https://openapi-ts.dev/introduction). Runtime validation is a separate trial requirement.
- Effect tracks declared expected errors in its error channel. Defects and interruption are separate: [Effect Expected Errors](https://effect.website/docs/v4/error-management/expected-errors). The trial must test both declared failures and defects.
- SQLite permits one simultaneous write transaction. `BEGIN` transactions do not nest, and a busy commit can leave the transaction active: [SQLite Transactions](https://www.sqlite.org/lang_transaction.html). Releasing an inner savepoint is not a durable outer commit: [SQLite Savepoints](https://www.sqlite.org/lang_savepoint.html).
- Browser contexts isolate cookies and storage: [Playwright Isolation](https://playwright.dev/docs/browser-contexts). Service workers can hide routed requests: [Playwright Network](https://playwright.dev/docs/network#missing-network-events-and-service-workers).

These sources explain mechanisms. They do not demonstrate that a particular integration works with the project's installed versions.

### 5. Separate intended behavior from existing defects

Before any implementation, freeze a short case manifest. Each case records its input, expected output/state, source and classification:

- **Contract:** intended behavior supported by the current contract and reviewed rules.
- **Characterization:** observed behavior whose intent needs a decision.
- **Known or suspected defect:** a mismatch, not a requirement to reproduce silently.
- **Infrastructure limitation:** a missing tool, unstable harness or unavailable environment.

Two concrete examples matter:

1. The server emits `invalid_due` and `time_zone_unavailable`, but the frontend rejection-code list omits them: [src/api/ops.py:620–651](src/api/ops.py#L620-L651); [frontend/src/lib/data/types.ts:240–269](frontend/src/lib/data/types.ts#L240-L269). This is confirmed declaration drift. A trial should detect it, not delete these server answers to fit the copied union.
2. Successful JSON is asserted as `T`; an unreadable successful answer becomes an `ApiError` with the successful status. That status is not retryable under the current rule: [frontend/src/lib/data/api.ts:39–103](frontend/src/lib/data/api.ts#L39-L103). Combined with queue removal, this is a source-derived unknown-outcome risk, not a reproduced incident.

Historical sign-in and rejection-persistence failures remain historical evidence. They do not establish the current failure rate or cause: [docs/background/test-suite-review.md:200–236](docs/background/test-suite-review.md#L200-L236).

Do not make Python's output the sole oracle. Check it against the intended contract. If a disputed behavior affects the mandatory slice, resolve it through an approved small repair or report that part of the comparison as blocked. Keep the original failing assertion and evidence. Do not turn a known failure into a pass by adding waits, skips or broad normalization.

## Proposed bounded trial

### A. Comparison arms

| Arm | Scope | Purpose |
|---|---|---|
| P0 | Fixed existing Python app and current Svelte client | Record present behavior and feedback. This is the control, not an assumed perfect implementation. |
| P1 | Python with precise types for the slice, generated wire declarations and runtime decoding | Test the smallest no-rewrite improvement. Count generation and schema-maintenance work. |
| T1 | Strict TypeScript with runtime schemas and plain service/result interfaces | Test language/code-sharing benefits against P1. Use one server layout and one SQLite driver, chosen before coding. |
| T2, conditional | T1 with Effect only at transaction/error and SSE-lifetime boundaries | Test Effect's added value without changing domain rules, frontend or SQL semantics. |

**Recommended order:** P0/P1 first. T1 needs separate stack/trial approval. T2 needs a further decision after T1 exists. Do not build both SvelteKit routes and a separate TypeScript API merely to complete the matrix. A separate API needs a concrete requirement; a second HTTP-framework comparison can wait.

For runtime parity, use the same frozen Svelte build. For contract-change tasks, use the same Svelte source and feature behavior; allow only the contract imports, generated files and boundary decoding needed by each arm. Record these differences and their cost. Do not attribute a shared browser fix to the backend language.

No React, ORM, database replacement, WAL switch, frontend Effect adoption, SSR rewrite or deployment change belongs in this slice.

### B. Minimum functional surface

Use two synthetic rooms, two lists in one room, a public link for one list, an unrelated room member and two independent browser sessions. Seed ordinary, date-only and timed items.

Implement only the support needed for:

- Room sign-in, session read and sign-out.
- Authorized room and shared-list changes feeds and SSE.
- `item.edit` with the existing fields and rules.
- `item.quantity_delta` as a small non-idempotent retry sentinel. A duplicate edit can hide double execution; a duplicate increment cannot.

Fixture controls may revoke a room token or rotate a share link. They must change the real disposable database through its controlled owner. They are test controls, not new public production endpoints. Other app features are out of scope and must be listed as unsupported, not mocked as passing.

### C. Shared contract cases

Freeze these groups before agent work. Run the same inputs and assertions against every applicable arm:

| Group | Required assertions |
|---|---|
| C1: authorized read | A member gets the full snapshot, then the correct delta. Shared reads contain only the shared list and no room navigation/metadata. Unknown room and invalid room credential retain the non-revealing refusal. |
| C2: unauthorized write | Missing/wrong/revoked room access changes nothing. Cross-room and cross-list IDs cannot escape their scope. A share link cannot perform room management. Access is checked before replay. |
| C3: fresh edit | Name, notes, quantity and due fields save together. Response envelope, result sequence, feed values and headers match the declared API. An invalid or duplicate edit changes none of those fields. |
| C4: stale edit | A late different edit returns HTTP 200, `rejected`, `changed_meanwhile`, with unchanged row and sequence. The already-stored wanted values remain an applied exception. |
| C5: field presence | Omitted quantity keeps it. Omitted due fields keep them. Explicit date/time nulls clear the correct dependent fields. A name-only edit retains an unchanged timed schedule. Invalid due combinations and unavailable zones retain their distinct answers. |
| C6: replay | Same ID/body replays applied and rejected answers after a process restart, without another mutation or sequence event. Changed body or room returns 409. HTTP failures are not stored and can be retried after correction. |
| C7: lost answer | Let the real server commit, then drop the answer. Retry the identical ID/body. The delta applies once. The browser queue survives reload and settles after recovery. |
| C8: transaction failure | Inject failure after an early write and before completion. No partial item, sequence or replay row remains. A later valid write succeeds. Also exercise lock timeout and commit-failure cleanup. |
| C9: SSE | Initial current sequence; committed change visible through the feed; no uncommitted notice; no consecutive duplicate sequence; no unrelated-room/list disclosure; initial refusal is JSON; revocation closes the stream; disconnect/reconnect releases capacity and recovers state. |
| C10: browser offline path | Edit while disconnected, reload with the pending edit retained, reconnect, validate session and fetch feed before sending. A conflict remains visible after reload and is not silently resent as a new operation. |
| C11: browser integration | Session A edits; session B updates through SSE/feed. Use real controls, distinct storage and error capture. Keep existing accessible labels and error presentation. |
| C12: compatibility guard | Preserve API version 4 and its response header for unchanged behavior. A clearly different version stops writes, retains waiting work and still permits sign-out. Test missing/malformed headers according to the existing rule. |

For same-runtime replay, retain the existing byte-equality assertion. For a cross-runtime migration, require the declared stored-answer representation and replay bytes to remain compatible; do not normalize away a difference before deciding whether it affects existing clients.

Allow normalization only for predeclared generated IDs, controlled timestamps and irrelevant HTTP header ordering. Do not normalize away status codes, missing/null fields, error codes, scope, sequence changes or replay differences.

Use bounded waits and causal barriers for positive events. Retain the stated limits of existing negative observation windows; an idle interval does not prove that a request can never occur later. Native cleanup probes can supplement the common HTTP assertions. SSE suppression alone cannot prove that an internal notification callback was never invoked.

### D. Browser coverage without a suite overhaul

Reuse four narrow journeys: online edit/live update, stale conflict, offline reload/reconnect, and committed-write/lost-answer replay. Run them on Chromium, Firefox and WebKit. Reuse the existing real-worker saved-shell case as a separate check.

Use routing-based faults without service workers only where interception requires it, as the current reconnect tests already do: [browser_tests/test_svelte_offline_reconnect.py:24–26](browser_tests/test_svelte_offline_reconnect.py#L24-L26). Do not claim that such a run proves service-worker behavior. For the real-worker case, use server stop/restart or a transport fault outside browser routing.

Keep the current smoke, engine and device policy. The full browser suite remains broader feedback, not a newly invented release gate: [docs/browser-testing.md:60–118](docs/browser-testing.md#L60-L118). No routine phone check or staging environment is added.

### E. Isolation and reproducibility

Before an approved trial starts, record:

- Exact baseline and candidate commit IDs, clean/dirty state, lockfiles, runtime/checker/driver versions and commands.
- One synthetic seed specification and a baseline-schema fixture created without production data.
- A separate closed seed copy, database path, backup path, port, browser profile and logs for every arm and attempt. Never let two implementations use one database file.
- The same schema, triggers, rollback journal, one-second lock wait, one app instance and equivalent password-hashing cost. Do not improve performance by disabling integrity rules or weakening authentication.
- The same CPU/memory environment, locale, time zone, worker count and browser versions. Record concurrent load. Run measured suites one at a time.

Use the existing default test policy for app verification. Use a declared serial configuration for the small HTTP trial where that improves comparability. Do not compare an eight-worker Python suite with a serial Node subset and label the difference a backend speed result.

Setup, package installation, generation, build, lint/type checks, focused tests and broad verification are separate measurements. No packages are installed under this research authorization.

## Deliberate mistakes and comparable agent tasks

### Fault catalog

Prepare equivalent faults outside the accepted candidate. Inject one at a time. Keep tests fixed. Restore the source and verify the clean result after each probe.

| Fault | What the trial measures |
|---|---|
| Put a string where a numeric `base_seq` is required in authored code | Whether static feedback identifies the exact boundary and expected type. |
| Misspell a rejection discriminator or omit one union branch | Whether code vocabulary and exhaustiveness checks catch drift. |
| Remove the database/access dependency from the write use case | Whether service wiring fails clearly before a request, or only at runtime. |
| Return a successful answer with a missing or string sequence | Whether runtime decoding catches actual malformed output; static assertions alone must not earn credit. |
| Add an expected infrastructure failure without updating HTTP mapping | How plain result unions, Python types and Effect's error channel expose the omission. |
| Throw an unexpected defect instead of an expected failure | Whether diagnostics preserve the cause without disguising it as a business rejection or retry loop. |
| Bypass the stale-version check or move access validation outside the protected write | Whether behavior tests catch a real rule violation that types cannot prove. |
| Fail after an early SQL write or near commit | Whether rollback, replay state and later connection usability are verified. |
| Lose an answer after commit; separately fail successful-answer decoding | Whether durable operation identity is retained and recovery is bounded. Never count current queue removal as the desired result. |
| Omit SSE cleanup | Whether disconnect/capacity assertions expose the resource leak. |

Not every mistake should be caught statically. Record the **first detecting layer**, exact diagnostic, file/line accuracy, false leads, commands, repair turns and final behavior. A generic failed test is useful protection but is not the same feedback quality as a precise type error.

For an unresolved current defect, record P0 as failing or not protected. An improved client policy must be common to the improved arms and separately costed. Do not quietly fix it only in the favored stack.

### Matched work packets

After equivalent clean slice implementations exist, give fresh agents the same three outcome-based tasks:

1. **Contract change:** make an additive item-edit result change in the disposable trial and update its browser consumer. Preserve older stored answers that lack the new optional field. Count all independently edited contract definitions and generation steps.
2. **Rule repair:** diagnose a seeded stale-edit failure while retaining the same-value exception. Do not disclose the implementation location.
3. **Lifecycle diagnosis:** find and repair a seeded transaction or SSE cleanup failure from the same external symptom and equivalent logs.

Use two independent attempts per task and arm, with equivalent alternate seeds. Use the same model, reasoning tier, tools, documentation access and prompt structure. Record effective settings. Counterbalance execution order. Agents must not see another arm's solution. Use a fresh reviewer for each result.

Separate initial port/setup effort from these maintenance tasks, but retain it in the adoption cost. Incomplete attempts remain incomplete results; do not exclude them from the denominator. Any retry uses the same declared retry policy in each arm.

This report does not launch or authorize those agents. Model choices and execution approval remain with the owner and runner.

## Trial scorecard and predeclared decisions

The following thresholds are **proposed decision rules**, not measured facts or new deployment gates. Freeze or amend them with the owner before implementation, not after seeing a preferred result.

### Mandatory correctness conditions

A candidate cannot win unless:

- Every mandatory slice assertion passes for intended behavior, with no new skip, relaxed assertion or hidden retry.
- Authorization, atomicity, replay and pending-work retention have no unresolved failure.
- Each deliberate behavior fault is caught by its intended protection. Restore checks pass afterward.
- The owner can trace access, stale rejection, rollback/commit, replay and notification in the actual code.
- Unsupported features and incomplete migration checks are explicit.

Baseline failures remain visible. An unrelated historical/full-suite failure is not automatically a new production gate. A failure inside the trial's mandatory slice prevents a parity claim until resolved or the trial is reported inconclusive.

### Measured scorecard

| Dimension | Weight | Record |
|---|---:|---|
| Owner readability | 30 | After the same short introduction, the owner explains the five paths above and locates the relevant code. Record correct explanations, hints needed and unfamiliar concepts. This is a code-learning exercise, not routine manual device testing. |
| Debugging effort | 25 | Per matched attempt: active diagnosis/repair time, agent turns, check cycles, wrong hypotheses, reviewer corrections and unresolved defects. |
| Feedback quality | 20 | For each fault: first detecting layer, diagnostic specificity, repair usefulness and misses. Keep static, runtime-schema and behavior-test catches separate. |
| Change/maintenance cost | 15 | Initial setup/port work; files and contract definitions edited; generated versus handwritten code; new dependencies; adapters and unsafe escapes. |
| Check/runtime cost | 10 | Setup/build/generation/check times; focused-test elapsed time; request and SSE delay; startup/shutdown; memory and browser bundle impact. |

Score each dimension from 0 to 4 using a frozen rubric: 0 = unusable/incomplete, 1 = materially worse, 2 = comparable, 3 = clear improvement, 4 = clear improvement repeated across both attempts without a new tradeoff. Compute `sum(weight × score / 4)`. Keep the raw evidence beside the score; the total is not a correctness proof.

**Proposed advance rule:** a more complex arm must pass correctness, score at least ten points above its simpler comparator, and show a repeated debugging or feedback improvement without worse owner readability. Compare T1 with P1, and T2 with T1. A tie, inconsistent benefit or missing evidence means keep the simpler option. Passing the slice authorizes only a recommendation for the next decision, never a full rewrite.

### Cost measurements

- For clean check/runtime timings, use one warm-up and five measured runs per arm. Preserve every outcome. Report median and range, not only the fastest run.
- Use the same synthetic data and a fixed light workload: two writer sessions editing separate items, with two SSE listeners. Record the exact request count and pacing before measurement.
- Include a separate lock-contention probe with the same lock-holder schedule. Report whether HTTP/SSE remains responsive and whether recovery releases the connection.
- Record both normal request latency and commit-to-observer update delay. A faster HTTP answer that delays notifications is not an unqualified win.
- Separate cold startup/setup from warm checks. Use production-cost hashing for authentication measurements.
- As a conservative proposed default, reject a greater-than-twofold increase in recurring focused-check time, request/update latency or peak memory unless the owner explicitly accepts the measured tradeoff. Do not treat this broad threshold as a performance target.

Five runs and two agent attempts give local comparison evidence, not a universal speed or reliability claim. Preserve first failures; a rerun pass is not a clean first pass. This follows [docs/testing.md:49–61](docs/testing.md#L49-L61).

### Stop conditions

Stop or narrow the affected arm when:

- It needs a frontend rewrite, new database or wider feature port to complete the declared slice.
- It cannot preserve authorization, data integrity, replay identity or browser pending work.
- Passing requires weaker tests, disabled triggers, changed journal mode or reduced password cost.
- A required driver/runtime/tool is unavailable under the approved permissions.
- An unresolved baseline defect or harness problem prevents a fair result.
- The bounded packets are complete and show no clear advantage.

Do not keep adding features, frameworks or fault seeds until a desired stack wins. There is no research elapsed-time or spend cap imposed here; the finite scope is the stopping boundary.

## Later migration checks — not trial implementation

A successful slice is insufficient to replace the full server. A later, separately approved migration task must cover the following using **synthetic disposable data only**:

| Area | Required compatibility evidence |
|---|---|
| Room passwords | Legacy bcrypt hashes verify in the new runtime; new hashes verify in the old runtime if rollback is claimed. Check UTF-8, byte-length boundaries, invalid inputs, failure behavior and hashing cost. Do not silently change truncation or encoding behavior. Current hashing is in [src/password_hashing.py:8–13](src/password_hashing.py#L8-L13). |
| Room cookies/tokens | Preserve names derived from the slug, token hashing/storage, lifetimes, revocation and HTTP/HTTPS name separation. Keep Secure, HttpOnly, SameSite, Path and no-Domain behavior. Test setting and clearing, not just login. See [src/room_cookies.py:7–33](src/room_cookies.py#L7-L33), [src/api/cookies.py:15–54](src/api/cookies.py#L15-L54), and existing [tests/test_cookie_headers.py:1–145](tests/test_cookie_headers.py#L1-L145). |
| Admin/device access | Admin signing uses its own scrypt-derived HMAC format, expiry and password-change invalidation; admin access must not become room access. Device/enrollment cookies and revocation need their own compatibility tests. See [src/admin_access.py:1–99](src/admin_access.py#L1-L99) and [ARCHITECTURE.md:44–68](ARCHITECTURE.md#L44-L68). |
| Cached clients | An already-open page, installed worker, saved snapshot and pending sent/unsent/rejected operations survive server replacement as declared. Test both old-client/new-server and rollback-client/server combinations. Preserve old URL handling and `/sw.js`; a forced reload is not a substitute for retaining queued work. |
| API version | Preserve the current number for compatible behavior. For a breaking change, exercise the version guard and unsent-work message. A mismatch is detected only after an answer; it does not make a breaking first write safe. See [src/api/version.py:1–10](src/api/version.py#L1-L10), [frontend/src/lib/data/compat.svelte.ts:1–83](frontend/src/lib/data/compat.svelte.ts#L1-L83), and [frontend/src/lib/data/api.ts:45–81](frontend/src/lib/data/api.ts#L45-L81). |
| Replay compatibility | Old canonical hashes, UUID handling, Unicode/numbers, missing/null fields and stored answer forms remain valid. Existing applied and rejected operations do not execute again after replacement. Respect the 30-day retention boundary and old-operation holds. |
| Schema/storage | Preserve `user_version`, deployed migration order, constraints, triggers, IDs, sequences, deletions, replay rows and private reminder state. Verify startup on old synthetic schemas and refusal of a newer unsupported schema. Include safe integer boundaries and date/time representations. |
| Name rules | Connections that insert/rename items must supply the registered trim/lower functions with equivalent semantics. Check Unicode key metadata and collision refusal, not only ASCII examples. See [src/item_names.py:6–38](src/item_names.py#L6-L38) and [src/database_setup.py:1076–1164](src/database_setup.py#L1076-L1164). |
| Rollback | Test old runtime opening the candidate's written synthetic database only where compatibility is claimed. A newer schema can require matching code and backup restoration, not code rollback alone. Restoring a backup loses writes made after it; retained client operation IDs and server replay history can also diverge. Document that limit. Do not promise lossless rollback. |
| Runtime/deployment | Preserve one instance, one origin, volume path, rollback journal, lock wait, health, proxy/origin handling, graceful shutdown and SSE reconnect. Test local startup behavior; do not claim it proves Railway HTTPS behavior. |

Current migration and recovery limits are already documented: [docs/deployment.md:95–133](docs/deployment.md#L95-L133). Do not invent a second recovery policy or extra staging gate. Use the existing automated checks, backup/deploy process and owner approvals when that later task is authorized.

## Arguments for and against

### For this trial

- It measures work the app actually does, including its failure paths.
- Stronger Python contracts remain a real competitor rather than a token baseline.
- A frozen browser/API contract reduces framework and UI bias.
- Deliberate faults show where feedback arrives, not merely how many tests pass.
- Separate setup and maintenance costs expose the price of a port.
- Selective Effect can demonstrate dependency/error/cleanup benefits without receiving credit for rules it does not supply.

### Against or limits

- A small slice cannot establish whole-app migration safety.
- The mature Python baseline and a new port have unequal history. Separate setup accounting helps but does not remove this difference.
- Owner learning and agent familiarity affect results. Counterbalanced order and fresh attempts reduce, not eliminate, that bias.
- A backend-neutral adapter has a cost and can contain mistakes. It needs review and must not replace existing native tests wholesale.
- Weighted scores contain judgment. Raw evidence and the simpler-option default are more important than a small numerical lead.
- For this small app, even running T1/T2 may cost more than fixing the demonstrated contract weaknesses.

## Recommendation

1. Keep Python, SQLite, Svelte and the current API now.
2. Ask for approval of the small P0/P1 contract trial first. Freeze its case manifest and decision rules before coding.
3. Use this report's common slice if a TypeScript comparison is separately approved. Select one server layout and driver, not a framework tournament.
4. Evaluate Effect only against a working plain-TypeScript slice and only at the stated server boundaries.
5. Keep suite review, lint audits and test-removal decisions with their existing tasks. Better types do not remove authorization, transaction, replay, migration or real-browser tests.
6. Stop with the simpler stack if the bounded evidence does not show a clear owner-relevant benefit.

## Unknowns

- No commands, application tests, builds, type checks, benchmarks or fault probes ran here.
- The supplied checkout revision and installed dependencies were not independently verified.
- No baseline failure rate, agent-effort measure or owner comprehension score was collected.
- No generated contract pipeline, TypeScript driver or server adapter was selected or tested.
- Native HTTP/ASGI test adaptation, commit-failure injection and stream cleanup probes still need implementation design and review.
- The unknown-write-outcome path is a source-derived risk, not a reproduced production incident.
- Cross-runtime passwords, cookies, canonical hashes, Unicode, schema, time-zone and cached-client compatibility remain unverified.
- The score weights and thresholds are proposals. The owner must freeze them before an approved trial.
- External sources move. They must be checked against pinned versions before implementation. The normal Pydantic documentation fetch refused a cross-origin redirect; its official repository documentation supplied the needed evidence instead.
- Production data, credentials, private auth stores and device behavior were not inspected.

## Handoff

**Runner/reviewer:** this source-level research deliverable is ready for independent review. `status: complete` does not mean that review passed, the bead closed or implementation was accepted. Check the scope, contract/bug distinction, finite packets, decision rules and migration limits.

**Owner:** the next decision is whether to approve P0/P1 only, or also a bounded T1 trial. No stack choice or rewrite is presumed. Existing gates remain in [docs/scope.md:39–57](docs/scope.md#L39-L57).

**Next-task packet:** preserve the supplied baseline, freeze the case/fault manifest, select synthetic fixture ownership, declare tools and versions, agree thresholds, and implement only the narrow adapter and approved comparison arms. Return raw results, first failures, independent review, changed files and unsupported areas. Do not open a second suite-overhaul task.

**Related-task relay:** send confirmed rejection-code drift and unknown-write-outcome requirements to `lr-347.4.3`; leave strict-flag counts and lint recommendations with `lr-347.4.3`/`lr-347.4.4`.

**Prerequisites used:** all supplied summaries; full `lr-d80.json`, `lr-9o2.json` and `related-tasks.json` under `/home/hsa/.local/share/list-app-stack-research/phase-one/`. Their recommendations informed this design; decisive local and external sources were inspected directly.

**Execution record:** the required subagent diagnostic ran. No agents were launched. No shell commands, file changes, installations, Beads writes, version-control changes, servers, application checks or deployments were performed.
