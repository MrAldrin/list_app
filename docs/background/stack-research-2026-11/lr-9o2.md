## Summary

**Supplied baseline:** `3ff346236bb3efaa01d8ec2fe923f971c4797845`.

**Inspected workspace:** `/home/hsa/projects/list_app-stack-lr-9o2`.

Keep Python, SQLite, Svelte and the current API. The evidence does not justify a backend rewrite to obtain Effect.

Effect is a TypeScript library for describing work, its expected failures and its required services. It also supplies tools for cleanup, concurrency and retries. Its strongest possible benefit here is a consistent way to compose server infrastructure. It does not replace the application's rules.

If the owner later approves a TypeScript server trial, compare these options on the same operation:

- **Plain strict TypeScript:** runtime schemas, tagged result values, passed-in service interfaces and explicit transaction helpers.
- **Selective Effect:** the same domain rules and wire answers, with typed failure channels, service requirements and scoped resource management.

For this small app, plain TypeScript is the lower-complexity starting point. Effect must show a clear benefit over that option, not merely over unchecked JavaScript.

This is a completed source-level research deliverable for the runner's independent review. It is not bead closure, implementation approval, stack acceptance or deployment approval.

## Evidence

### 1. Method and baseline

I read the supplied bead, prerequisite summaries, the full `lr-d80` evidence where relevant, and the related-task snapshot. I inspected decisive repository sources and official external sources myself. The supplied worker report was a lead, not proof.

Repository citations below refer to the inspected workspace and supplied baseline. Shell and version-control commands were prohibited, so I did not independently verify the checkout hash.

The current backend is Python/FastAPI. SQLite stores the data. Svelte runs the browser interface. One server process serves the API and static frontend: [ARCHITECTURE.md:9–30](ARCHITECTURE.md#L9-L30). The frontend already enables strict TypeScript: [frontend/tsconfig.json:1–8](frontend/tsconfig.json#L1-L8).

### 2. Actual failures and concrete weaknesses

These findings have different evidence levels. They must not be presented as one set of current production bugs.

| Finding | Evidence level | What it says about Effect |
|---|---|---|
| Earlier write paths could lose concurrent tag changes, leak an integrity error, or leave failed transactions open. | Historical audit records deterministic reproductions and fixes. Some paths belonged to the removed NiceGUI interface. | Transaction ownership and intent-based updates matter. Effect could help standardize cleanup, but would not invent the correct update or identity rule. |
| An earlier offline experiment failed the owner's real-use expectations and was rolled back. | Owner-reported outcome. The retained review did not establish a root cause. | Server Effect adoption does not establish browser storage, installed-app startup or offline synchronization reliability. |
| The server emits `invalid_due` and `time_zone_unavailable`, but the frontend rejection-code union omits them. | Directly confirmed declaration drift. Production impact was not reproduced. | A shared or generated runtime contract can address this without Effect. An Effect error channel alone would not update the browser's wire-answer union. |
| The shared API client asserts successful JSON as `T` without checking its shape. | Direct source observation. | Runtime schemas are useful independently of Effect. |
| An unreadable successful write answer becomes an `ApiError` with the successful HTTP status. That is not retryable under the current queue policy, so the queue can remove the operation despite an uncertain server outcome. | Source-derived failure path; not reproduced in this session. A newly added decoder could create the same risk if it throws an ordinary error. | Naming an unknown write outcome is useful. Effect does not decide the safe queue policy automatically. |

Sources:

- Historical transaction findings: [docs/background/write-atomicity-findings.md:11–30](docs/background/write-atomicity-findings.md#L11-L30). Do not treat its old unresolved-item statements as a fresh audit of the current API.
- Historical offline outcome and evidence limits: [docs/background/offline-findings.md:5–18](docs/background/offline-findings.md#L5-L18).
- Rejection drift: [src/api/ops.py:620–651](src/api/ops.py#L620-L651), [frontend/src/lib/data/types.ts:240–269](frontend/src/lib/data/types.ts#L240-L269).
- Successful-response assertion and unreadable answer: [frontend/src/lib/data/api.ts:64–103](frontend/src/lib/data/api.ts#L64-L103).
- Retry classification: [frontend/src/lib/data/api.ts:39–43](frontend/src/lib/data/api.ts#L39-L43).
- Queue removal and retry paths: [frontend/src/lib/data/write-queue.ts:414–464](frontend/src/lib/data/write-queue.ts#L414-L464).

No inspected evidence establishes that a current production failure requires Effect or a language change.

### 3. Expected errors, business answers, defects and interruption

Effect describes a computation as `Effect<Success, Error, Requirements>`. Its expected errors compose into a union. Defects remain outside that typed error channel. See [Expected Errors](https://effect.website/docs/v4/error-management/expected-errors) and [Unexpected Errors](https://effect.website/docs/v4/error-management/unexpected-errors).

For ListR, use these distinctions:

| Category | Example | Preserve this behavior |
|---|---|---|
| Expected request failure | Invalid input; missing room access; reused operation ID with another body | Map to the existing 422, 401 or 409 HTTP contract. Do not store it as an operation answer. |
| Business answer | `changed_meanwhile`, `duplicate_name`, or `invalid_due` | Return HTTP 200 with `status: rejected`. Roll back attempted operation changes, then store the rejection for replay. |
| Expected infrastructure failure | A database lock cannot be obtained within the allowed wait | Map to the existing unavailable response. Retry only when its cause and replay boundary make retry safe. |
| Defect | A programming error or broken invariant | Report it and return the safe 500 response at the HTTP boundary. Do not disguise it as a business rejection or blindly retry it. |
| Interruption | A request or stream is cancelled | Clean up resources. Do not assume cancellation proves that a write did not commit. |
| Unknown write outcome | Commit may have succeeded, but the browser cannot read or validate the answer | Retain the same operation identity and body for recovery. This is not proof of write failure. |

The existing code already makes important distinctions. Applied and rejected answers are stored; HTTP errors are not: [src/api/idempotency.py:1–6,48–76](src/api/idempotency.py#L1-L76). Business rejection handling surrounds a savepoint: [src/api/ops.py:810–833](src/api/ops.py#L810-L833). Unhandled SQLite errors map to 503; other unhandled exceptions map to 500: [src/api/errors.py:127–131](src/api/errors.py#L127-L131).

**Important limit:** the current broad SQLite-to-503 mapping is not proof that every SQL error is transient. A future adapter must not label constraint errors or corrupted data as safe automatic retries.

Plain TypeScript can express expected failures with a discriminated `Result` union. Ordinary `Promise<T>` does not declare its rejection type. Effect adds automatic composition of the declared failure channel; it does not eliminate undeclared throws or defects.

### 4. One real workflow, both ways

Use the existing room `POST /api/v1/rooms/{slug}/ops` path with `item.edit`.

Current behavior includes:

1. Parse the operation.
2. Begin the write transaction and check current room access inside it.
3. Check the operation ID, room and canonical request hash.
4. Replay an existing answer, or apply the edit under a savepoint.
5. Reject stale, different edits; permit an edit whose wanted values are already stored.
6. Keep absent due fields distinct from explicit nulls.
7. Store the applied or rejected answer in the outer transaction.
8. Commit, then notify live streams only for a new applied answer.

Sources: [src/api/ops.py:654–707](src/api/ops.py#L654-L707), [src/api/ops.py:810–882](src/api/ops.py#L810-L882), [src/api/access.py:59–103](src/api/access.py#L59-L103), [src/api/idempotency.py:22–76](src/api/idempotency.py#L22-L76).

The sketches below are explanatory pseudocode. Custom helpers are proposed interfaces, not existing TypeScript code. Neither sketch was compiled or run.

#### Plain strict TypeScript plus a runtime schema

```ts
async function postEdit(raw: unknown, request: Request, deps: Services) {
  const parsed = EditSchema.safeParse(raw);
  if (!parsed.success) return invalidRequest422();
  const op = parsed.data;

  return httpBoundary(async () => {
    const done = await deps.db.withWriteTransaction(async (tx) => {
      const scope = await deps.access.checkInside(tx, request);
      const result = await runOnce(tx, scope.roomId, op, () =>
        editInSavepoint(tx, scope, op)
      );
      return { ...result, roomId: scope.roomId };
    });

    if (!done.replayed && done.answer.status === "applied") {
      deps.live.notify(done.roomId);
    }
    return done.answer;
  });
}
```

The runtime schema validates actual input. Zod's `safeParse`, for example, returns a success/error union: [Zod basic usage](https://zod.dev/basics).

`httpBoundary` must classify caught `unknown` values. Alternatively, the service interfaces can return explicit `Result<A, E>` values for expected failures. The team must choose and apply one convention consistently.

#### Selective Effect

```ts
const postEdit = (raw: unknown, request: Request) =>
  Effect.gen(function* () {
    const op = yield* decodeEdit(raw);
    const db = yield* Database;
    const access = yield* RoomAccess;

    const done = yield* db.withWriteTransaction((tx) =>
      Effect.gen(function* () {
        const scope = yield* access.checkInside(tx, request);
        const result = yield* runOnceEffect(tx, scope.roomId, op, () =>
          editInSavepointEffect(tx, scope, op)
        );
        return { ...result, roomId: scope.roomId };
      })
    );

    if (!done.replayed && done.answer.status === "applied") {
      const live = yield* LiveUpdates;
      yield* live.notify(done.roomId);
    }
    return done.answer;
  });
```

A proposed public type would resemble:

```ts
Effect<Answer,
  InvalidInput | AccessDenied | OpIdReused | DatabaseUnavailable,
  Database | RoomAccess | LiveUpdates>
```

A single HTTP adapter maps those expected failures to the existing wire errors. Defects are logged and handled separately at that boundary. Effect Schema can supply the decoder, but using it does not require adopting Effect throughout the browser: [Schema introduction](https://effect.website/docs/v4/schema/introduction).

#### The difficult helper contracts are the same

Neither sketch makes the hard work disappear:

- `withWriteTransaction` owns the connection for the whole operation and returns only after commit.
- Access is checked **inside** that transaction, before replay lookup. Moving it outside creates a revocation race.
- `runOnce` validates the room and request hash, and stores both kinds of business answer atomically.
- The savepoint helper rolls back attempted operation changes before converting a business rejection to normal answer data. Converting every failure to success inside a transaction would risk committing partial work.
- Database failures and defects escape the business-rejection conversion and roll back the outer transaction.
- Validation and serialization must preserve existing hash, absent/null and stored-answer rules.
- Notification is after commit. Its failure cannot undo an already committed write.

The current implementation centralizes transaction ownership with a reentrant lock and `BEGIN IMMEDIATE`, with rollback on any exception: [src/database_crud.py:40–68](src/database_crud.py#L40-L68).

Effect makes error and service composition more explicit. Plain TypeScript makes control flow more familiar. Neither proves these helper contracts correct.

### 5. Database services and resource lifetime

Current database access uses imported module state and a shared connection: [src/database_crud.py:1–40](src/database_crud.py#L1-L40). Passing a small database interface is a valid plain-TypeScript alternative to that coupling.

Effect's `Context.Service` records required services in the computation type. `Layer` constructs and supplies implementations. This can help when database, access and live-update services must be replaced together in tests. Sources: [Managing Services](https://effect.website/docs/v4/requirements-management/services), [Managing Layers](https://effect.website/docs/v4/requirements-management/layers).

Effect also has an existing SQL abstraction. Its documented transaction wrapper commits on success and rolls back on failure or interruption, with savepoints for nested transactions. Its SQLite acquisition support serializes a shared connection and handles failed-commit cleanup: [SqlClient API](https://effect.website/docs/v4/api/effect/sql/SqlClient).

This is a real argument for Effect. A fair comparison must not pretend that all transaction machinery must be written from scratch with it.

But the documented SQL interfaces are marked **unstable**. The Node SQLite adapter also defaults to WAL and a five-second busy timeout: [SqliteClient API](https://effect.website/docs/v4/api/sql-sqlite-node/SqliteClient). ListR documents rollback journaling and a one-second lock wait: [docs/deployment.md:112–122](docs/deployment.md#L112-L122).

Thus an adapter's defaults are not baseline parity. A later trial must explicitly configure and test transaction mode, lock wait, foreign keys, savepoints, commit-failure cleanup, stored hashes and SQLite-specific functions. Effect does not justify changing the journal mode as a hidden part of adoption.

Wrapping a synchronous SQLite call in Effect does not make that call non-blocking. Fibers are managed tasks, not automatically database worker threads.

### 6. Cancellation and SSE

The current SSE path already has explicit lifetime management:

- Reserve capacity before opening the stream.
- Check access before sending stream headers.
- Subscribe before the first sequence read.
- Recheck access and sequence on wakes and at least every 15 seconds.
- Perform short database reads in a worker thread.
- Release subscriptions and reservations when the stream closes.

Sources: [src/api/events.py:34–145](src/api/events.py#L34-L145), [src/live_updates.py:58–129](src/live_updates.py#L58-L129).

Effect's `Scope` and `acquireRelease` can bind reservations, subscriptions and child tasks to a stream's lifetime. Finalizers run when that scope closes, including on interruption: [Scope](https://effect.website/docs/v4/resource-management/scope).

Plain TypeScript can express the same ownership with `try/finally`, an abort signal, and an explicit subscription object.

For either design:

- The HTTP adapter must connect client disconnect and server shutdown to cancellation.
- The underlying operation must support cancellation. Interrupting an Effect does not undo an arbitrary external operation.
- A write cancelled near commit can have an unknown outcome.
- Do not hold a database transaction open for the life of an SSE stream.
- Closing a resource scope is not, by itself, proof that every task using it was stopped.

The official Effect API documents an `AbortSignal` argument for `tryPromise`; it must be forwarded to a supporting operation. The API also warns that signal delivery depends on declaring the callback parameter normally: [Effect API: tryPromise](https://effect.website/docs/v4/api/effect/Effect#tryPromise). A search-generated claim that v4 `tryPromise` lacks that signal was contradicted by this inspected API and was not used.

The best possible SSE benefit is less repeated lifetime code. There is no evidence here that the present cleanup code is broken or that Effect would preserve all SSE behavior automatically.

### 7. Retry safety and durable offline idempotency

Effect's retry operators rerun work after selected typed failures. They support limits and schedules. They do not establish idempotency: [Retrying](https://effect.website/docs/v4/error-management/retrying).

ListR's retry safety comes from durable application state:

- The browser stores an operation and marks it sent before the request leaves.
- Retryable unanswered requests retain their identity.
- The server checks and stores the operation answer in the write transaction.
- Replays do not apply or notify again.

Sources: [frontend/src/lib/data/write-queue.ts:399–464](frontend/src/lib/data/write-queue.ts#L399-L464), [src/api/idempotency.py:48–76](src/api/idempotency.py#L48-L76), [tests/test_api_idempotency.py:264–280](tests/test_api_idempotency.py#L264-L280).

**The guarantee has a retention boundary.** Server records older than 30 days can be pruned; a pruned ID can run again as a new operation. The browser holds old pending operations for an explicit decision. See [tests/test_api_idempotency.py:375–404](tests/test_api_idempotency.py#L375-L404), [frontend/src/lib/data/queue-entries.ts:8–12,132–159](frontend/src/lib/data/queue-entries.ts#L8-L159). Do not describe this as unconditional exactly-once execution forever.

A selective Effect design should not add a blanket retry around the route or an individual mutating SQL statement. Retry only a complete safe unit, with the same operation ID and body, after cleanup. Do not retry business rejections, authorization failures, defects or permanent SQL errors as if they were temporary network failures.

An in-memory Effect schedule does not replace IndexedDB persistence, queue ordering, reload recovery, API-version checks or old-operation holds. Frontend Effect adoption is a separate decision.

### 8. Learning, debugging and escape hatches

| Area | Plain strict TypeScript | Selective Effect |
|---|---|---|
| Basic control flow | Familiar `async/await`, tagged unions and `try/finally`. | Adds generators, effect values and a managed runtime. Describing work is distinct from running it. |
| Expected errors | Explicit result types work well, but thrown Promise failures are not tracked by `Promise<T>`. | Expected errors compose in the `Error` type. Tagged recovery can retain unhandled cases. |
| Dependencies | Pass interfaces directly or through a small services object. | Learn service keys, requirements, layers and layer lifetime. |
| Debugging | Follow ordinary calls and caught values. | Also inspect fiber exits, causes, interruption and finalizers. HTTP-boundary diagnostics must preserve useful causes. |
| Small changes | Usually fewer concepts and less setup. | Can be simpler once several services share the same conventions; can be more machinery for a short handler. |
| Escape hatches | `any`, assertions and unchecked JSON can bypass checks. | The same TypeScript escapes remain. Incorrect constructors and recovery operators can also hide meaningful failure information. |

Specific Effect risks:

- `Effect.promise` treats unexpected rejection as a defect. Use the correct constructor and classify foreign-library failures deliberately.
- `orDie` removes failures from the typed channel; it does not remove the failure.
- Broad `catchCause` recovery can turn defects or interruption into apparent success. Inside a transaction, that can change commit behavior.
- Running nested Effects as detached Promises or detached tasks can lose the intended request context and cancellation ownership.
- Calling a raw database connection outside the service boundary bypasses the design.
- An error channel of `never` does not prove that a computation cannot fail. Defects and interruption still exist.

Sources: [Creating Effects](https://effect.website/docs/v4/getting-started/creating-effects), [Unexpected Errors](https://effect.website/docs/v4/error-management/unexpected-errors), [Effect runPromise/runPromiseExit API](https://effect.website/docs/v4/api/effect/Effect#runPromiseExit).

These are learning and review costs, not measured development-time results. There is no evidence here that agents or the owner will make fewer mistakes with Effect.

### 9. Version compatibility and maintenance

External observations made during this research:

- The publisher has released Effect 4.0. Its release page promises support for 4.x and warns that unstable or experimental modules may change in minor or patch releases: [Effect 4.0](https://effect.website/blog/releases/effect/40/).
- The fetched npm metadata reports `effect` **4.1.3**: [registry metadata](https://registry.npmjs.org/effect/latest).
- The fetched Node SQLite adapter is **4.1.3**, with an `effect: ^4.1.3` peer requirement: [SQLite package metadata](https://registry.npmjs.org/@effect/sql-sqlite-node/latest).
- The fetched `@effect/platform-node` **4.1.3** metadata requires Node **>=22.19.0** and Effect `^4.1.3`: [platform package metadata](https://registry.npmjs.org/@effect/platform-node/latest).
- The general installation guide states TypeScript **5.9+**, recommends TypeScript 7 for its tooling, and gives a broader Node 18+ statement: [installation](https://effect.website/docs/v4/getting-started/installation). That broad statement must not override a selected adapter's stricter requirements.
- Effect Schema requires strict mode and documents an optional `exactOptionalPropertyTypes` setting. Static and runtime acceptance can differ without that setting: [Schema requirements](https://effect.website/docs/v4/schema/introduction#requirements).

Local observations:

- The frontend declares TypeScript `^6.0.3` and does not declare Effect: [frontend/package.json:17–40](frontend/package.json#L17-L40).
- Node 24 builds the frontend, but the production image runs Python. A Node build stage is not an existing Node backend runtime: [Dockerfile:1–23](Dockerfile#L1-L23).

A future trial must pin compatible package versions, choose the runtime and driver, and use matching-major documentation. Do not mix v3 tutorials with v4 service, schema or error-handling APIs. The TypeScript declaration meets the documented minimum in principle; it is not a completed compatibility test.

The registry `latest` endpoints and website documentation are moving sources. The observed version values are recorded here; no packages were installed or verified locally.

### 10. Test implications

Effect can make service substitution and controlled time easier. Its TestClock advances Effect time without real waits: [TestClock](https://effect.website/docs/v4/testing/testclock). Plain interfaces and an injected clock can provide similar test seams.

Neither replaces these behavior tests:

| Boundary | Required evidence in any later comparison |
|---|---|
| Authorization | Missing access, wrong room/list, reset public link, and revocation before replay. A supplied database service is not proof of permission. |
| Transaction | Rollback after partial work, failed commit cleanup, savepoint rejection, and a later successful write. |
| Replay | Same ID/body returns the stored answer without a second mutation or notification; changed body/room is rejected. |
| Edit rules | Stale different values reject; already-stored wanted values succeed; absent/null due fields retain their meaning. |
| SSE | Initial JSON refusal, capacity limit, disconnect cleanup, revocation, sequence scope and shutdown. |
| Unknown outcome | Lost or invalid successful answer retains recoverable operation identity. |
| Cancellation | Before acquisition, during work and near commit; no leaked reservation, transaction or connection ownership. |

Existing sources provide useful cases, not passing results from this session:

- Replay and HTTP-error behavior: [tests/test_api_idempotency.py:264–360](tests/test_api_idempotency.py#L264-L360).
- Two-client stale-action behavior: [tests/test_api_concurrency.py:185–250](tests/test_api_concurrency.py#L185-L250).
- Real stream/disconnect harness and leak assertions: [tests/test_api_events.py:38–173](tests/test_api_events.py#L38-L173).

Use real SQLite and HTTP integration tests for behavior that test doubles cannot establish. A successful layer-based unit test does not prove SQL, proxy, stream or browser behavior. No test-removal claim is made.

## Arguments for and against

### For selective Effect in a future TypeScript server

- Expected failures remain visible as operations compose.
- Required services are recorded in types rather than informal module conventions.
- Scopes and finalizers give one resource-lifetime model.
- Existing SQL transaction machinery may reduce custom infrastructure code.
- Controlled clocks and service layers can make some tests easier to write.

### Against adoption now

- The server is Python. Obtaining these benefits first requires a separately justified port.
- The app is small, and its owner is learning. Plain interfaces, schemas and result unions may be easier to understand.
- Confirmed contract drift does not require Effect to fix.
- Current transaction and SSE ownership are already explicit.
- Effect adds another execution and debugging model, plus adapter/version maintenance.
- The attractive SQL interfaces have unstable markers and defaults that differ from ListR.
- No trial has shown lower learning cost, fewer defects, faster changes or better runtime behavior.

## Recommendation

**Adopt no Effect in the current server.** Keep the no-rewrite option from `lr-d80` as the baseline.

If a TypeScript backend trial is approved for separate reasons, evaluate Effect only at these server boundaries:

1. **Transaction and database ownership:** one tested service controls acquisition, transaction, savepoints and cleanup. Compare the existing Effect SQL support with a small plain helper; do not assume either is correct by construction.
2. **Foreign-library error mapping:** classify expected database or transport failures once, near the adapter. Preserve defects rather than calling every exception retryable.
3. **SSE lifetime:** one stream scope owns its reservation, subscription and child work. Keep database reads short and separate from stream lifetime.
4. **HTTP execution boundary:** provide services and run the Effect once per request or stream. Map expected failures and defects to the existing contract without leaking internal details.

Do not add Effect merely for:

- Pure item/date/name rules.
- Static DTO declarations.
- A schema decoder that can stand alone.
- Simple synchronous transformations.
- Browser persistence and durable replay.
- A claim that authorization or behavior tests are no longer needed.

Keep frontend adoption separate. Sharing browser-safe schemas does not require sharing the server runtime, and server services must not enter the browser bundle.

For a later approved trial, use the same edit and replay cases in both designs. Record:

- Setup and change-review effort.
- Time to diagnose an injected database failure and cancelled stream.
- Number of error mappings, dependency-wiring steps and unsafe escapes.
- Type-check/test cost and event-loop delay during database lock waits.
- Whether the owner can explain access, rollback, commit, replay and cleanup without relying on framework slogans.

Require behavior parity before drawing a benefit claim. Prefer plain TypeScript if Effect adds concepts without removing meaningful repeated work. Stop the trial if it cannot preserve the contract or show a clear maintenance benefit. These are proposed comparison measures, not executed results or extra deployment gates.

## Unknowns

- The supplied checkout hash and installed dependency versions were not independently verified.
- No TypeScript server framework, deployment runtime or SQLite driver is selected.
- No explanatory sketch was compiled.
- No application tests, linters, type checks, builds or benchmarks were run.
- Cancellation behavior at the HTTP/driver boundary remains untested.
- Cross-runtime request hashes, numeric behavior, Unicode rules, time zones and existing replay rows remain compatibility work for any port.
- Owner learning time and agent debugging quality are unmeasured.
- Historical offline failure has no established root cause in the evidence inspected here.
- Declaration drift and the unreadable-answer queue path were not reproduced as production incidents.
- External documentation may move. Package and adapter behavior must be checked against pinned versions before implementation.

## Handoff

**Runner and independent reviewer:** review this report and preserve its evidence levels and unrun-check limits. `status: complete` means the research is ready for review, not that independent review passed or the bead was closed.

**Owner decision:** no Effect adoption is recommended now. A TypeScript trial, package changes and stack acceptance still need the existing approval under [docs/scope.md:39–57](docs/scope.md#L39-L57).

**Next stack comparison:** carry forward the no-rewrite baseline, the two equivalent workflow designs, the unstable SQL/default-configuration findings and the measurable trial criteria. Do not count framework-provided cleanup as proof of authorization or durable idempotency.

**Owner relay to `lr-347.4.3`:** use the confirmed rejection-code drift and uncertain successful-write-answer path. Keep its strict-flag counts and full frontend-contract audit with that task.

**Owner relay to `lr-347.4.4`:** no lint audit was duplicated. A check for unsafe assertions, floating Promises or raw database escapes may support a later design, but cannot prove transaction or permission behavior.

**Execution record:** the required subagent diagnostic ran. No agents were launched. No shell commands, file changes, package installations, Beads writes, version-control changes, servers, application checks or deployments were performed.
