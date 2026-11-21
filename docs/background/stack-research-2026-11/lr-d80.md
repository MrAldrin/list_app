## Summary

**Supplied baseline:** `3ff346236bb3efaa01d8ec2fe923f971c4797845`.

**Inspected workspace:** `/home/hsa/projects/list_app-stack-lr-d80`.

Keep Python, SQLite, Svelte, and the current API as the baseline.

The clearest improvement is a better contract between server and browser. A contract states which fields a request or answer contains. It can generate TypeScript declarations and support runtime checks. This does not require a backend rewrite.

A TypeScript backend offers more direct code reuse: server and browser can import the same schemas and some pure functions. That benefit is real but limited. The server must still check credentials, read current database state, apply conflict rules, commit changes, and store replay answers. A shared type cannot do those jobs.

**Recommendation:** first consider a separately approved, narrow contract trial on the existing Python backend. Do not select SvelteKit server routes or a separate TypeScript API without evidence that this smaller option is insufficient.

This is a research deliverable, not implementation approval, bead closure, acceptance, or deployment approval.

## Evidence

### 1. Method and prerequisite reuse

I read the supplied bead, prerequisite reports, and related-task snapshots. I then inspected the decisive code and official external sources myself.

Prerequisite evidence reused:

- `/home/hsa/.local/share/list-app-stack-research/phase-one/lr-ngj.json`: current boundaries, authorization, replay, and three comparison workflows.
- `/home/hsa/.local/share/list-app-stack-research/phase-one/lr-48d.json`: TypeScript is already strict; runtime schemas are separate from static types; podcast preference is not rewrite evidence.
- `/home/hsa/.local/share/list-app-stack-research/phase-one/related-tasks.json`: `lr-347.4.3` and `lr-347.4.4` remain open in the supplied snapshot. No completed findings were supplied.

I did not repeat their planned checker-count, lint-rule, mutation, or test-removal audits. Live coordination was prohibited. The handoff below identifies the overlap and the remaining gaps for owner relay.

All repository links below are relative to the inspected workspace. Shell and version-control commands were prohibited, so the checkout hash was not independently verified. These findings describe the inspected source associated with the supplied baseline.

### 2. What exists now

| Boundary | Observation | Contract consequence |
|---|---|---|
| Request input | Pydantic models use a `type` discriminator, strict scalar types, and forbidden extra fields. | Python already has meaningful runtime input validation. |
| Handler dispatch | The handler registry accepts `Any`; handlers return broad dictionaries. | Validated input does not produce fully checked internal results. |
| Successful API response | `Api.request<T>` reads JSON and returns `data as T`. | The assertion does not validate the received shape. |
| Operation result | Python uses `dict[str, Any]`; TypeScript uses `Record<string, unknown>` for applied results. | A generated broad dictionary would preserve the weak boundary. |
| Stored browser data | Queue and snapshot readers perform their own checks and compatibility handling. | Network, storage, and authoring contracts are not interchangeable. |
| Private reminders | Their frontend adapter already validates several successful responses and preserves unknown write outcomes. | There is an existing local pattern to learn from; validation is not absent everywhere. |

Sources: [src/api/requests.py:18–25](src/api/requests.py#L18-L25), [src/api/ops.py:163–372](src/api/ops.py#L163-L372), [src/api/ops.py:744–882](src/api/ops.py#L744-L882), [src/api/idempotency.py:19–45](src/api/idempotency.py#L19-L45), [frontend/src/lib/data/api.ts:64–103](frontend/src/lib/data/api.ts#L64-L103), [frontend/src/lib/data/types.ts:249–282](frontend/src/lib/data/types.ts#L249-L282), [frontend/src/lib/data/queue-entries.ts:17–159](frontend/src/lib/data/queue-entries.ts#L17-L159), [frontend/src/lib/data/snapshot-validate.ts:59–178](frontend/src/lib/data/snapshot-validate.ts#L59-L178), [frontend/src/lib/reminders/api.ts:31–169](frontend/src/lib/reminders/api.ts#L31-L169).

**Confirmed drift:** the server emits `invalid_due` and `time_zone_unavailable`, but the frontend rejection-code list omits them. I confirmed the prerequisite finding directly: [src/api/ops.py:623–652](src/api/ops.py#L623-L652), [frontend/src/lib/data/types.ts:249–262](frontend/src/lib/data/types.ts#L249-L262). This is declaration drift. Its production impact was not reproduced.

Strict TypeScript is already enabled: [frontend/tsconfig.json:1–8](frontend/tsconfig.json#L1-L8). The project also configures Ruff, pytest, and `ty` for `src/`: [pyproject.toml:15–80](pyproject.toml#L15-L80). Neither language option starts from an unchecked baseline.

### 3. Side-by-side: an actual item-edit workflow

The dialog saves name, description, quantity, date, time, and zone together. It starts from the values shown when opened. Tags save separately. See [frontend/src/lib/list/ItemDialog.svelte:1–104](frontend/src/lib/list/ItemDialog.svelte#L1-L104).

A representative request follows the existing `ItemEdit` contract. The identifiers and sequence below are illustrative, not captured user data:

```json
{
  "op_id": "11111111-1111-4111-8111-111111111111",
  "type": "item.edit",
  "list_uid": "22222222-2222-4222-8222-222222222222",
  "item_uid": "33333333-3333-4333-8333-333333333333",
  "name": "oat milk",
  "description": "cold",
  "quantity": 2,
  "date": null,
  "base_seq": 12
}
```

`date: null` clears the date and its dependent time and zone. Omitting all due fields keeps the stored schedule. Omitting quantity, or sending quantity as null, keeps quantity. These are different rules, not one generic optional-field rule.

The existing Python and TypeScript declarations already describe much of the same request:

| Part | Python today | TypeScript today | Stronger-contract option |
|---|---|---|---|
| Operation identity | `Literal["item.edit"]`, canonicalized UUID fields | `'item.edit'`, ordinary strings | Generate the wire union; keep UUID parsing at runtime. |
| Quantity | Strict integer, bounded to ±1,000,000; optional/null | `number`, optional/null | Runtime integer and range checks; a TypeScript `number` alone is insufficient. |
| Due fields | Nullable strings with validators; presence tracked through `model_fields_set` | Optional nullable strings | Preserve absent versus null without adding defaults during decoding. |
| Base version | Required strict non-negative integer | Required `number` | Runtime range checks plus the existing stored-state comparison. |
| Output | `{"changed_seq": ...}` inside an applied envelope | Broad result record | Define an item-edit result schema and connect it to the sent operation. |

Sources: [src/api/ops.py:95–160](src/api/ops.py#L95-L160), [src/api/ops.py:279–308](src/api/ops.py#L279-L308), [frontend/src/lib/data/types.ts:151–177](frontend/src/lib/data/types.ts#L151-L177).

#### Equivalent server paths

The TypeScript columns below are proposals, not existing code or tested implementations.

| Step | Keep Python with stronger contracts | SvelteKit server routes | Separate TypeScript API |
|---|---|---|---|
| HTTP entry | Keep `POST /api/v1/rooms/{slug}/ops`. | Add a corresponding `+server.ts` POST route. | Define the same route in the chosen Node HTTP framework. |
| Parse | Keep bounded JSON reading and Pydantic `parse_op`. | Read bounded JSON and call a shared runtime schema. | Same shared runtime schema. |
| Authorize | Keep `room_access(..., write=True)`. | Server-only transaction helper checks the room cookie and token row. | Same server-only use case behind a different HTTP adapter. |
| Apply | Keep the item-edit rules; replace selected broad internal dictionaries with precise types. | Server-only use case reads stored item state and applies the same rules. | Same use case; no need to duplicate rules in HTTP handlers. |
| Commit and replay | Keep access check, operation, savepoint, and stored answer in one transaction. | Must implement equivalent transaction ownership and replay behavior. | Must implement the same behavior. |
| Answer | Explicit output schema, without changing the wire shape. | Serialize a schema-checked result in the existing envelope. | Same output contract. |
| Notify | Wake SSE after commit. | Wake SSE after commit. | Wake SSE after commit. |

SvelteKit supplies HTTP route types and `Response` handling. It does not infer or validate arbitrary JSON request bodies merely because a handler is a `RequestHandler`. Its own routing example reads `request.json()` without a runtime schema: [SvelteKit routing](https://svelte.dev/docs/kit/routing#server).

#### Outcomes all options must preserve

- **Fresh edit:** normalize and save the requested values together; return an applied answer with `result.changed_seq` and the scope's `seq`.
- **Stale, different edit:** return HTTP 200 with `status: rejected` and `code: changed_meanwhile`; do not change the item.
- **Stale, same values:** succeed when the stored values already match the requested values.
- **Lost answer:** retry the same ID and body; return the stored answer without applying the edit again.
- **Unchanged timed schedule:** keep its stored UTC instant and cycle. A name edit must not depend on currently available zone data.

The current logic is directly visible in [src/api/ops.py:446–457](src/api/ops.py#L446-L457), [src/api/ops.py:655–709](src/api/ops.py#L655-L709), [src/database_crud.py:682–761](src/database_crud.py#L682-L761), and [src/api/idempotency.py:48–76](src/api/idempotency.py#L48-L76).

Inspected test examples include `test_stale_edit_after_someone_renamed_is_rejected` and `test_edit_that_wants_the_stored_values_is_applied`: [tests/test_api_conflicts.py:196–225](tests/test_api_conflicts.py#L196-L225). Replay cases compare response bytes and database snapshots: [tests/test_api_idempotency.py:264–299](tests/test_api_idempotency.py#L264-L299). These tests were not run.

### 4. Side-by-side: authorization and a public-link edit

The same valid item-edit body can be sent through a room route or a public share route. Its schema does not establish permission.

| Case | Python today | Required in either TypeScript option |
|---|---|---|
| Room request without valid room access | 401 `not_authenticated`; unknown room and invalid access look alike. | Check the credential against current database state, not a browser boolean. |
| Public link edits its own list | Allowed operation type; scope limits lookup to the shared list. | Shared schema can parse the body, but server scope must enforce list ownership. |
| Public link names another list | Business rejection `list_unavailable`. | Preserve the same non-revealing answer and no write. |
| Public link requests room management | 422 `invalid_request`. | Keep a server-enforced operation allowlist. A UI restriction is not enough. |
| Link reset before a retry | Old token fails access before a stored operation answer can be replayed. | Authorize inside the transaction before replay lookup. |
| Admin signs in | Separate admin credential; it does not grant room access. | Keep separate authorization paths rather than one generic logged-in state. |
| Personal reminder policy | Room access plus installation/enrollment ownership and target checks. | Do not expose it through public-list permissions or shared feeds. |

Sources: [src/api/access.py:59–149](src/api/access.py#L59-L149), [src/database_crud.py:132–151](src/database_crud.py#L132-L151), [src/database_crud.py:843–884](src/database_crud.py#L843-L884), [src/api/ops.py:387–433](src/api/ops.py#L387-L433), [src/api/ops.py:767–882](src/api/ops.py#L767-L882), [src/api/admin.py:54–76](src/api/admin.py#L54-L76), [src/api/reminder_policies.py:80–115](src/api/reminder_policies.py#L80-L115).

The share feed also deliberately hides room navigation and unrelated list data: [src/api/share.py:40–86](src/api/share.py#L40-L86). Inspected tests cover a real share-holder item edit, the lack of room access, metadata hiding, and reset behavior: [tests/test_api_share.py:199–246](tests/test_api_share.py#L199-L246), [tests/test_api_share.py:400–455](tests/test_api_share.py#L400-L455), [tests/test_api_share.py:490–524](tests/test_api_share.py#L490-L524).

**Implication:** a shared `Scope` type can help server developers use the right values. It cannot make a client-supplied room or list ID trustworthy. Database checks and authorization tests remain necessary in all three options.

### 5. File-level candidate reuse map

“Shared” below means safe code or contract reuse. It does not mean private values become public. Proposed files do not exist yet.

| Existing sources | Candidate reuse | Keep separate or server-only |
|---|---|---|
| `src/api/ops.py:163–372`; `frontend/src/lib/data/types.ts:84–238` | Operation names, wire fields, optional/null shape, scalar constraints. Python can export schema; TypeScript can import a common runtime schema. | Server handlers, field-presence bookkeeping, authorization, and request-hash policy. Keep client authoring types distinct where they intentionally use a narrower subset of accepted wire input. |
| `src/api/ops.py:791–833`; `frontend/src/lib/data/types.ts:240–282` | Applied/rejected envelopes, rejection codes, and explicit result schemas. | Stored replay rows and transaction control. The current response does not include operation type; correlate a result with the sent operation rather than silently changing the API. |
| `src/api/errors.py:27–77`; `frontend/src/lib/data/types.ts:284–378`; `frontend/src/lib/data/result.ts:15–76` | HTTP error envelope and server code vocabulary. | HTTP status mapping and safe server messages. Browser-only action codes, such as local storage or session-transition failures, remain client contracts. |
| `src/api/changes.py:28–55`; `src/api/share.py:56–86`; `frontend/src/lib/data/types.ts:3–82` | Room, list, item, deletion, and feed output schemas. | SQL reads and scope-based redaction. A public shape must not contain database credentials, token rows, or internal reminder-cycle fields. |
| `src/field_limits.py:9–25`; `frontend/src/lib/ui/field-limits.ts:1–20` | Current public text limits and validation messages where appropriate. Python can generate constants; TypeScript can import a small shared module. | Count queries and enforcement stay on the server. Historical migration constants stay frozen rather than importing changing runtime rules. |
| `src/api/ops.py:118–145`; `frontend/src/lib/data/item-date.ts:1–19` | Calendar-date and clock-time shape checks. A TypeScript backend could use the same pure parser as the browser. | Authoritative time-zone resolution and stored UTC values stay on the server. Regex alone does not prove a calendar date exists. |
| `src/reminders/due_schedule.py:100–159`; `frontend/src/lib/data/overlay.ts:359–458` | A pure merge of date/time/zone intent could be shared in a TypeScript design. | `due_at`, cycle generation, cycle start, and authoritative conflict comparison. Browser projections remain provisional. |
| `src/item_names.py:6–38`; `frontend/src/lib/data/overlay.ts:80–123` | Name trimming and duplicate-key calculation are potential pure-rule reuse. | SQLite function registration, stored keys, and key-version metadata. A JavaScript port is not proved equivalent to Python Unicode behavior. |
| `src/item_visibility.py:5–25`; `frontend/src/lib/data/visibility.ts:8–27` | Modes, defaults, bounds, and settings validation. | Actual hiding is already a browser rule, not a duplicated server filter. Do not move it to the server merely to create reuse. |
| `src/reminders/rules.py:57–155`; `frontend/src/lib/reminders/rules.ts:1–35`; `frontend/src/lib/reminders/api.ts:8–29,171–198` | Public/private DTO declarations, relative-rule units and limits, and selected pure normalization helpers. | Ownership checks, activation decisions, fixed-rule identity, trusted stored rules, server clock, and authoritative resolved instants. Client input and server-normalized output remain different schemas. |
| `frontend/src/lib/data/queue-entries.ts:17–159`; `frontend/src/lib/data/snapshot-validate.ts:59–178` | Reuse scalar parsers and current wire sub-schemas where compatible. | Queue format, age holds, sent state, old-snapshot defaults, and storage recovery remain browser-specific. A current network schema must not replace the storage compatibility reader wholesale. |
| `frontend/src/lib/data/overlay.ts:14–34,125–165`; `frontend/src/lib/data/rebase.ts`; `frontend/src/lib/data/write-queue.ts:365–507` | Existing pure helpers may remain reusable TypeScript modules. | Queue scheduling, IndexedDB, uncertain projections, and rebasing are not server transaction rules. Moving the backend does not remove them. |
| `src/api/access.py`; `src/api/session.py`; `src/api/admin.py`; `src/api/reminder_policies.py:80–115` | Only request/response shapes and safe permission labels may cross the browser boundary. | Credential verification, cookies, token hashes, revocation, device ownership, and authorization decisions are server-only. |
| `src/database_crud.py:40–68`; `src/database_setup.py:1066–1198`; `src/api/idempotency.py` | SQL behavior and serialized fixtures can serve as port specifications. | Database connection, migrations, backups, triggers, savepoints, replay hashes, and stored answers are server-only. They are not browser-shareable code. |
| `src/api/events.py:34–145`; `frontend/src/lib/data/events.ts:1–58,179–195` | Event names and `seq` payload shape. | Subscription registry, access rechecks, timers, cancellation, and capacity are server runtime behavior. |

For Python, reuse is mainly **generated declarations, constraints, constants, and comparison fixtures**. Python functions do not become browser JavaScript by exporting JSON Schema.

For TypeScript, a proposed browser-safe `contracts` module could contain schemas and pure rules. SvelteKit database and credential modules should remain under `src/lib/server/` or use a `.server.ts` filename. SvelteKit checks illegal client imports, but its documentation says this detection is disabled in unit-test mode: [server-only modules](https://svelte.dev/docs/kit/server-only-modules). A separate API package needs an equally clear browser-safe export boundary; using the same language alone does not create one.

### 6. What generated Python contracts would require

**Proposal, not an existing generation pipeline:**

1. Keep the existing Pydantic operation models as the input source of truth.
2. Add precise output and error contracts for a small chosen boundary.
3. Export schemas locally, without requiring production access or publishing API documentation.
4. Generate TypeScript declarations from those schemas.
5. Add a runtime decoder where untrusted JSON enters the browser.
6. Check that regeneration produces no unexpected contract diff.

Pydantic supports `TypeAdapter.json_schema()` for unions and distinguishes validation from serialization schemas: [official JSON Schema documentation source](https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/json_schema.md). OpenAPI TypeScript supports OpenAPI 3.0/3.1 and discriminators, but explicitly generates **runtime-free types**: [openapi-typescript](https://openapi-ts.dev/introduction).

There are important limits:

- **No ready-made complete OpenAPI contract was established.** This app disables its public OpenAPI URL and manually reads request JSON. `post_op` receives a dependency-provided dictionary and calls `parse_op` itself: [src/server.py:68–80](src/server.py#L68-L80), [src/api/requests.py:53–78](src/api/requests.py#L53-L78), [src/api/ops.py:861–882](src/api/ops.py#L861-L882). Merely turning an OpenAPI URL on would not connect all these manual models and broad responses. FastAPI documents explicit schema metadata for manually processed bodies: [advanced configuration](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/#custom-openapi-path-operation-schema).
- **Custom validators are code, not portable schemas.** UUID canonicalization, calendar validation, normalization, and cross-field rules need explicit schema detail or separate checks. Pydantic's own documentation shows custom validation that produces only a basic string schema: [JSON Schema documentation source](https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/json_schema.md). Do not assume exporting an `AfterValidator` exports its implementation.
- **Static types lose numeric constraints.** JSON Schema integer/range checks still become ordinary TypeScript numbers unless additional runtime or branded-type handling is used.
- **Generated types do not check responses at runtime.** A generated fetch client's static inference is useful, but is not a substitute for a decoder.
- **Output validation can change behavior.** FastAPI response models validate and filter output: [response-model guide](https://fastapi.tiangolo.com/tutorial/response-model/). Introducing them carelessly can strip fields, add defaults, change serialized replay answers, or report an output error after a write has committed. A later trial must decide where validation happens and preserve current replay behavior.
- **Model imports are not a proven safe export path.** The current operation module imports database and server services. A small contract-only module may be useful. Do not boot the real application merely to generate a schema; startup requires an admin password and opens/migrates the database through its lifespan.

A JSON-Schema-first design is also possible, but would move contract ownership away from the existing models and require a second generation direction. For this MVP, that extra change is not yet justified.

### 7. Runtime parsing and error handling

A TypeScript schema can infer its static type and validate actual input. Zod documents `parse`, `safeParse`, and separate input/output types: [basic usage](https://zod.dev/basics). This could let a TypeScript server and browser import the same wire schema.

That is not automatic parity with the current API:

- Input objects must reject unknown fields, not silently strip them. Zod's default object behavior strips extra fields; strict objects differ: [JSON Schema conversion documentation](https://zod.dev/json-schema).
- A decoder must not insert optional defaults or trim strings in a way that changes a stored operation body.
- JSON Schema does not carry every transform or refinement. Zod documents unrepresentable types and an experimental JSON-Schema-to-Zod conversion. A Pydantic-to-Zod round trip must not be assumed complete or stable.
- JSON numbers differ across runtimes. Python integers, strict integer validation, SQLite's 64-bit integers, and JavaScript's safe integer range do not have identical limits. The current feed allows `since` up to `2**63 - 1`, while stored snapshot sequences use `Number.isSafeInteger`: [src/api/changes.py:22–33](src/api/changes.py#L22-L33), [frontend/src/lib/data/snapshot-validate.ts:40–42](frontend/src/lib/data/snapshot-validate.ts#L40-L42). A port needs an explicit compatibility decision, not silent rounding or a changed wire type.

#### Keep three failure classes separate

1. **HTTP failure:** for example 401, 422, or 503 with `{"error": ...}`. These are not stored operation rejections.
2. **Business rejection:** HTTP 200 with `status: rejected`. Its answer is stored for replay.
3. **Unknown write outcome:** the write may have committed, but the answer was lost, unreadable, or failed decoding.

This distinction matters immediately. The shared write queue currently removes an operation on a non-retryable exception. Its retry test covers network errors and HTTP 502/503/504. A new decoder that throws a generic error for an invalid successful write answer could send the operation down the removal path: [frontend/src/lib/data/api.ts:39–42,84–103](frontend/src/lib/data/api.ts#L39-L42), [frontend/src/lib/data/write-queue.ts:407–464](frontend/src/lib/data/write-queue.ts#L407-L464).

**Proposed rule:** a failed decoder after a possibly committed write must not be treated as proof that the write failed. Preserve the same operation ID and body, then use a bounded replay/recovery policy. Avoid endless retries on a permanently incompatible answer. The reminder adapter already names `UnknownWriteOutcome` and retains prepared writes: [frontend/src/lib/reminders/api.ts:31–33,108–169](frontend/src/lib/reminders/api.ts#L31-L33).

Also decide how to handle unknown future rejection codes. A strict decoder must not turn a valid business rejection from a newer server into lost queue state. Preserve the API-version check and explicit storage compatibility rules.

### 8. Transactions, async SQLite, and serialization

#### Current Python behavior

- One shared connection is protected by a process-local reentrant lock.
- Writes use `BEGIN IMMEDIATE`; errors roll back.
- Room/share authorization is checked inside that transaction.
- A savepoint lets a business rejection roll back its attempted work while the outer transaction stores the rejection answer.
- Notification happens after commit.

Sources: [src/database_crud.py:40–68](src/database_crud.py#L40-L68), [src/database_crud.py:132–151](src/database_crud.py#L132-L151), [src/database_crud.py:867–884](src/database_crud.py#L867-L884), [src/api/ops.py:810–858](src/api/ops.py#L810-L858).

The operation endpoint is a synchronous `def`. FastAPI runs such endpoints in its thread pool. SSE explicitly sends short database reads to a worker thread: [FastAPI async guide](https://fastapi.tiangolo.com/async/#path-operation-functions), [src/api/events.py:62–112](src/api/events.py#L62-L112). The baseline therefore does not need an async database rewrite merely because it uses asynchronous streams.

#### TypeScript implications

Node's `DatabaseSync` API is synchronous. Adding `async` to its caller or wrapping its result in a Promise does not make its SQLite work non-blocking. Node 24's documented default busy timeout is zero, unlike this app's one-second setting: [Node 24 SQLite](https://nodejs.org/docs/latest-v24.x/api/sqlite.html#class-databasesync), [docs/deployment.md:112–122](docs/deployment.md#L112-L122).

Two reasonable designs need comparison in any approved trial:

- **Synchronous transaction on the Node event loop:** simpler ownership; a lock wait or slow query also delays HTTP and SSE work. Suitability is unmeasured, not disproved.
- **Dedicated database worker or an async driver:** avoids blocking the HTTP event loop, but adds ownership, queueing, cancellation, and error-mapping code. Send a complete transactional operation to its owner. Do not let unrelated requests interleave statements on one shared connection between `await` points.

An async driver does not remove SQLite's single-writer rule. SQLite documents one simultaneous write transaction, `BEGIN IMMEDIATE`, and savepoints rather than nested `BEGIN`: [SQLite transactions](https://www.sqlite.org/lang_transaction.html).

Port requirements include the same transaction mode, timeout, rollback/savepoint behavior, foreign-key behavior, triggers, and safe parameter binding. No driver was installed or selected here.

#### Replay hashes are a migration boundary

The existing hash uses the validated Pydantic body, sorted compact JSON, UTF-8, and explicit legacy omission rules. `date: null` has a legacy hash omission rule; due-time and due-zone nulls are omitted only when unsent. These rules must not be flattened into one generic JSON serializer: [src/api/idempotency.py:22–45](src/api/idempotency.py#L22-L45), [src/api/ops.py:295–308](src/api/ops.py#L295-L308).

A TypeScript port needs compatibility fixtures for old bodies, canonical UUIDs, Unicode, numeric forms, absent/null fields, request hashes, and stored responses. Plain `JSON.stringify` is not evidence of compatibility with the existing Python canonicalization. Existing tests already exercise old null-field hashes and replay: [tests/test_api_conflicts.py:555–615](tests/test_api_conflicts.py#L555-L615).

Likewise, SQLite name guards call registered Python trim/lower functions. Key metadata can trigger an atomic rebuild when Python or Unicode semantics change: [src/item_names.py:6–38](src/item_names.py#L6-L38), [src/database_setup.py:1066–1120](src/database_setup.py#L1066-L1120). Sharing JavaScript normalization with the browser is useful, but it does not prove compatibility with existing stored keys.

### 9. SSE and Railway runtime

| Concern | Keep Python | SvelteKit server routes | Separate TypeScript API |
|---|---|---|---|
| Production server | Existing uvicorn/FastAPI process serves API and static Svelte files. | Requires a dynamic runtime adapter, such as adapter-node; static output alone cannot execute dynamic server routes. | Can keep the static Svelte build and serve it from one Node API process. A second production UI server is not required. |
| Rendering | Browser-only SPA. | Can remain browser-only; adding API routes does not require an SSR rewrite. | Browser-only SPA can remain unchanged. |
| SSE | Existing implementation supplies event encoding, keep-alives, capacity reservation, access rechecks, and cleanup. | A streamed `Response` is possible, but these application rules must be implemented. | Same application work, using the selected HTTP stack. |
| Database | Existing SQLite connection, migrations, and backup path. | Node driver and startup/migration integration need selection and verification. | Same database work; changing HTTP framework does not avoid it. |
| Same origin | Already one origin, no CORS. | Keep the current paths and origin rules. | Prefer one public origin. Separate Railway services would require deliberate proxy/routing and cookie design. |
| Restart | Existing one-second graceful shutdown and reconnect behavior. | Adapter-node has its own shutdown settings and cleanup hooks. | Selected server needs equivalent lifecycle handling. |

Local evidence: [Dockerfile:1–23](Dockerfile#L1-L23), [frontend/vite.config.ts:1–43](frontend/vite.config.ts#L1-L43), [frontend/src/routes/+layout.ts:1–4](frontend/src/routes/+layout.ts#L1-L4), [src/server.py:27–80](src/server.py#L27-L80), [src/main.py:31–45](src/main.py#L31-L45).

Official evidence: [SvelteKit static adapter](https://svelte.dev/docs/kit/adapter-static), [server routing and streamed responses](https://svelte.dev/docs/kit/routing#server), [adapter-node](https://svelte.dev/docs/kit/adapter-node).

All options must preserve these observed SSE rules:

- Authorize before starting the stream, so initial refusal is a JSON error.
- Reserve capacity, then subscribe before the initial sequence read.
- Send sequence notices, not row data; the browser fetches the feed.
- Recheck access at least every 15 seconds and after wakes.
- Send `revoked`, close on loss of access, and release capacity on disconnect.
- Notify only after commit; do not hold a database transaction for the stream lifetime.
- Preserve room versus shared-list sequence scope, reconnect refresh, and shutdown behavior.

Sources: [src/api/events.py:34–145](src/api/events.py#L34-L145), [src/live_updates.py:21–129](src/live_updates.py#L21-L129), [frontend/src/lib/data/events.ts:179–195](frontend/src/lib/data/events.ts#L179-L195), [docs/api-sync.md:44–79](docs/api-sync.md#L44-L79). SvelteKit's stream support is not proof that these rules are supplied automatically.

Railway does not create a language advantage here. The current deployment uses a persistent volume, one instance, no extra workers, and rollback journaling: [docs/deployment.md:112–133](docs/deployment.md#L112-L133). Railway documents that volumes cannot use replicas and that volume-backed redeployments have some downtime: [Railway volume reference](https://docs.railway.com/volumes/reference). Keep those limits in either language.

A Node design must also set the correct public origin and trust forwarded headers only from the real proxy. Adapter-node documents those controls, request-body limits, and shutdown behavior. Its default body limit is not this app's 64 KiB limit, and its default graceful shutdown is not this app's one-second setting. Default form CSRF protection must not be assumed equivalent to this app's exact-origin JSON-write check: [adapter-node](https://svelte.dev/docs/kit/adapter-node), [src/api/requests.py:14–64](src/api/requests.py#L14-L64).

## Arguments for and against

### Keep Python and strengthen contracts

**For:**

- Preserves tested behavior, migration code, and the current runtime.
- Can remove manually copied wire declarations and catch response drift.
- Keeps server rules in the language the project already uses.
- Allows runtime validation without changing Svelte or SQLite.

**Against:**

- Adds schema export, generation, and compatibility checks.
- Python and browser JavaScript still cannot share ordinary rule implementations.
- Custom validators and broad result dictionaries need deliberate work before useful generation.
- An inaccurate source schema can generate inaccurate types consistently.

### TypeScript in SvelteKit server routes

**For:**

- Browser and server can import one runtime schema and selected pure functions.
- Route code, UI, and server-only modules can stay in one application structure.
- Does not require React, SSR, a new database, or another public origin.

**Against:**

- Changes the production runtime and adapter.
- Requires ports of authorization, replay, migrations, SQLite functions, SSE, and lifecycle code.
- Server route types are not a complete network contract.
- Sharing code can blur server/browser boundaries unless imports and output projections remain explicit.

### Separate TypeScript API

**For:**

- Can share the same browser-safe schema package while keeping HTTP/backend concerns independent of SvelteKit.
- Could be justified by several clients, independent release needs, or a server framework with a required feature.
- Can still serve the static Svelte app from one Node service.

**Against:**

- Has the same core port cost as SvelteKit, plus API framework and package-boundary choices.
- Separate deployable services would add routing and operational work that this small app does not currently need.
- No inspected requirement establishes a need for independent API deployment or multiple client products.

No option removes authorization, transaction, replay, migration, offline, or browser tests merely by improving types. I make no test-removal claim.

## Recommendation

1. **Choose no rewrite for now.** The evidence shows a contract weakness, not a need to replace Python.
2. **Coordinate a small contract proposal with `lr-347.4.3`.** Start with explicit operation-answer/code schemas and one read decoder. Keep the existing transport and version checks. Assess a write decoder only with an explicit unknown-outcome policy.
3. **Use one contract owner.** Prefer the existing Pydantic input models for a Python trial. Generate browser declarations; do not maintain a second hand-copied schema and call it end-to-end safety.
4. **Strengthen selected Python internals too.** Precise item-state/result types and a checked dispatch approach can reduce `Any` without changing the backend language. Do not introduce a large type framework merely to remove a few dictionaries.
5. **If a later TypeScript trial is approved, compare one server use case behind two possible HTTP adapters.** Keep SQLite, the API, Svelte, and fixtures fixed. SvelteKit is the simpler candidate to investigate when one app owns UI and API; a separate API needs a concrete independent requirement.
6. **Do not add Effect, an ORM, WAL, a second origin, or React as a hidden dependency of this comparison.** None is required to share schemas.

Proposed trial measures, not executed results or new release gates:

- Number of independently edited contract definitions for one item-field change.
- Time and owner effort needed to understand and review that change.
- Generation/check time and added browser bundle size.
- Detection of malformed input and output without changing valid existing behavior.
- Preservation of stale-edit, same-value, replay, revocation, and absent/null cases.
- Preservation of queued operations when a write answer cannot be decoded.
- For Node only: HTTP/SSE responsiveness during database lock waits, and parity of startup, migration, hash, Unicode, and shutdown behavior.

Retain the project's existing automated release checks. This research adds no staging or routine manual-device gate. Any trial, package change, stack change, integration, or deployment still needs its existing approval under [docs/scope.md:39–57](docs/scope.md#L39-L57).

## Unknowns

- The supplied baseline hash and installed dependencies were not independently verified.
- No tests, builds, linters, type checks, schema generators, or benchmarks were run. Test references describe source, not passing results.
- The full effective TypeScript configuration and extra-flag error counts remain with `lr-347.4.3`.
- Rule coverage, lint costs, and tool findings remain with `lr-347.4.4`.
- No complete generated schema was produced. Custom-validator coverage and generation reproducibility remain unmeasured.
- No TypeScript SQLite driver or HTTP framework was selected or tested.
- Cross-runtime Unicode, numeric, canonical JSON, stored replay, and time-zone parity remain unverified.
- Node event-loop delay, browser decoder cost, bundle size, and owner learning cost remain unmeasured.
- Public documentation and raw upstream `main` files are moving sources, not proof of behavior for a pinned installed version. The normal Pydantic documentation fetch redirected; its official repository documentation was inspected instead.
- Production configuration, databases, credentials, private user data, and device behavior were not inspected.

## Handoff

**Runner and independent reviewer:** review this report before accepting the research. `status: complete` means the source-level research deliverable is ready; it does not mean the bead was closed or independent review passed. Preserve the baseline and unrun-check qualifications.

**Owner relay to `lr-347.4.3`:** use the confirmed rejection-code drift, broad operation result, manual request parsing, and separate storage compatibility contracts. Add the successful-write decoder/queue-removal risk to its contract design. Keep its planned strict-flag counts, detailed contract-test audit, and test-removal decisions there.

**Owner relay to `lr-347.4.4`:** no lint audit was duplicated. A future lint rule may help with unsafe assertions or unhandled promises, but it cannot establish runtime response shape or transaction ownership. Keep measured findings and rule recommendations with that task.

**Next stack research:** compare full adoption cost against this no-rewrite option. Do not count shared declarations as shared authorization, or fewer languages as proof of lower maintenance. Use the item-edit, replay, and link-revocation cases above as fixed behavior.

**Execution record:** the required subagent diagnostic ran. No agents were launched. No shell commands, file changes, package installations, Beads writes, version-control changes, servers, application checks, or deployments were performed.
