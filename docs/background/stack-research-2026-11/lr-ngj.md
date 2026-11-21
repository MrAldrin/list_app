## Summary

**Supplied baseline:** `3ff346236bb3efaa01d8ec2fe923f971c4797845`.

**Workspace inspected:** `/home/hsa/projects/list_app-stack-lr-ngj`.

ListR is a Svelte browser app served by one FastAPI process. It uses one SQLite connection, explicit transactions, and database triggers. Offline editing adds a second state system in the browser: saved server data, queued operations, and a temporary view of those operations.

The difficult parts are behavior contracts: which credential permits an action, what a retry means, how stale edits are rejected, and how an older installed app survives a deploy. A backend change would inherit these requirements.

**Observed problems:** the frontend rejection-code type omits two server codes; some documentation and comments describe older behavior. **Observed maintenance risks:** operation shapes, validation rules, and optimistic edits cross several manually maintained boundaries. **Not established:** current production failures, inadequate capacity, or lower maintenance cost from another stack.

Keep SQLite, Svelte, FastAPI, and the current API as the comparison baseline. This report is a research handoff, not approval to implement, accept, or deploy.

## Evidence

All repository references below are relative to the workspace above. They describe the inspected source view associated with the supplied baseline. Shell and version-control commands were prohibited, so I did not independently confirm the checkout hash. I inspected the decisive sources directly rather than treating the supplied worker reports as proof. No external web evidence was needed for this code map.

### 1. Runtime and code boundaries

| Boundary | Observed behavior | Main change risk |
|---|---|---|
| Browser → API | Components use a data layer. Requests use `/api/v1`, same-origin cookies, and JSON. Successful response JSON is cast to a TypeScript type, not checked against that type at runtime. | A server response change can pass through the client without a shape check. |
| API → rules | Pydantic validates discriminated write operations. Handlers apply business rules. | Request types do not provide end-to-end typing: responses and handler dispatch still use `Any` or generic dictionaries. |
| Rules → SQLite | A process-local lock protects a shared connection. Writes start `BEGIN IMMEDIATE`. Access checks and protected work share a transaction. | A new path must preserve transaction ownership and authorization ordering. |
| SQLite → clients | Triggers stamp row versions and record deletions. API writes wake streams after commit. | A table rebuild or direct write can affect synchronization even when the API shape stays unchanged. |
| Build → production | Node builds static Svelte files. The runtime image contains Python and the built files, not a second Node server. | Route handling, worker compatibility, and database migration must remain aligned. |

Sources: [src/server.py:35–84](src/server.py#L35-L84), [src/api/__init__.py:25–48](src/api/__init__.py#L25-L48), [src/api/requests.py:15–80](src/api/requests.py#L15-L80), [src/database_crud.py:40–68](src/database_crud.py#L40-L68), [src/api/ops.py:744–882](src/api/ops.py#L744-L882), [frontend/src/lib/data/api.ts:1–105](frontend/src/lib/data/api.ts#L1-L105), [Dockerfile:1–23](Dockerfile#L1-L23).

### 2. Authorization is several separate systems

- **Room access:** sign-in checks the room password and issues a random token in an HTTP-only cookie. SQLite stores its hash and authorization version. Private operations recheck the token inside their transaction. Password replacement removes old tokens and disables affected reminder grants. Expensive password checks run outside the database lock. Sources: [src/api/session.py:35–99](src/api/session.py#L35-L99), [src/api/access.py:59–126](src/api/access.py#L59-L126), [src/database_crud.py:843–884](src/database_crud.py#L843-L884), [src/database_crud.py:1236–1337](src/database_crud.py#L1236-L1337).
- **Admin access:** a separate signed cookie lasts 30 minutes. Its signing key is derived from `APP_PASSWORD` with scrypt. Admin sign-in does not issue room access. Admin routes enforce their own dependency. Admin sign-out clears the browser cookie; it is not the room-token revocation system. Sources: [src/admin_access.py:1–91](src/admin_access.py#L1-L91), [src/api/admin.py:48–136](src/api/admin.py#L48-L136).
- **Public share links:** the token permits reads and permitted writes for one list only. The feed returns a full list snapshot and hides room navigation unless the browser also has room access. Room members can rotate the token. The old token then fails before operation replay is consulted. Sources: [src/api/share.py:40–147](src/api/share.py#L40-L147), [src/api/ops.py:387–407](src/api/ops.py#L387-L407), [src/api/ops.py:774–882](src/api/ops.py#L774-L882).
- **Creation invitations:** admins issue reusable, expiring links. Invitation hashes are stored. Room creation rechecks expiry, revocation, and the creation limit inside the write transaction, after password hashing. Creating a room does not sign the visitor in. Sources: [src/room_invitations.py:20–139](src/room_invitations.py#L20-L139), [src/api/invitations.py:37–147](src/api/invitations.py#L37-L147).
- **Reminder device access:** the browser receives a random device secret in an HTTP-only cookie; SQLite stores its hash. Only explicit enrollment creates or resumes a grant. A saved grant depends on the installation lifetime, enrollment lifetime, authorizing room token, and room authorization version. Current API access still needs the room cookie. Sources: [src/reminders/identity.py:1–24](src/reminders/identity.py#L1-L24), [src/reminders/identity.py:93–133](src/reminders/identity.py#L93-L133), [src/reminders/identity.py:231–320](src/reminders/identity.py#L231-L320), [src/api/reminders.py:258–349](src/api/reminders.py#L258-L349).

Share tokens are stored directly in `lists.share_token`, unlike room, invitation, and device secrets. This supports reading the existing share link back to a room member. It is a real storage distinction, not proof of a security defect: [src/database_setup.py:113–150](src/database_setup.py#L113-L150), [src/api/share.py:114–121](src/api/share.py#L114-L121).

### 3. Schema, migrations, and hidden synchronization rules

The ordered migration list contains versions 1–18. Later migrations add durable identifiers, operation results, deletion records, tracking triggers, field guards, item-name keys, timed due dates, device enrollments, and private policies. The initial `CREATE TABLE` statements alone are not the current schema.

- Existing databases are backed up before pending migrations. Pending migrations run in one transaction, followed by integrity and foreign-key checks. Failure rolls back and prevents startup. Newer database versions are refused: [src/migrations.py:24–117](src/migrations.py#L24-L117).
- Tracking triggers generate identifiers, stamp row versions, and record deletions. Table rebuilds must preserve or recreate them: [src/database_setup.py:276–367](src/database_setup.py#L276-L367).
- Frozen field rules validate stored data before adding guards. Invalid rows stop the migration rather than being silently repaired: [src/database_setup.py:402–488](src/database_setup.py#L402-L488).
- Item-name uniqueness uses Python trim/lower functions registered with SQLite. A separate startup path can back up and rebuild keys when the algorithm or Unicode version changes. It refuses collisions: [src/item_names.py:1–38](src/item_names.py#L1-L38), [src/database_setup.py:1066–1159](src/database_setup.py#L1066-L1159).
- Personal policies use separate tables, scoped uniqueness, checks, and ownership triggers. They do not use shared change-tracking triggers: [src/database_setup.py:932–1033](src/database_setup.py#L932-L1033).

**Impact:** changing a field or normalization rule can require more than changing a model. It can affect stored keys, old queued requests, request hashes, triggers, backfills, and row versions. Historical migration constants must not be replaced casually with current runtime constants.

### 4. Item edits, offline replay, and conflicts

The item dialog preserves the draft opened by the user. Tags save separately. Tests specify when a tag-only update may advance the edit base without hiding another field change: [frontend/src/lib/list/ItemDialog.svelte:1–104](frontend/src/lib/list/ItemDialog.svelte#L1-L104), [frontend/src/lib/list/item-edit-base.test.ts:1–39](frontend/src/lib/list/item-edit-base.test.ts#L1-L39).

The browser keeps committed server snapshots separately from queued operations. Queue records are scoped by room or share token. Storage failure falls back to memory, which does not survive reload. Unknown queue formats are held, not sent. Pending operations older than 30 days need an explicit send choice: [frontend/src/lib/data/snapshot-store.ts:15–85](frontend/src/lib/data/snapshot-store.ts#L15-L85), [frontend/src/lib/data/queue-storage.ts:1–104](frontend/src/lib/data/queue-storage.ts#L1-L104), [frontend/src/lib/data/queue-entries.ts:8–159](frontend/src/lib/data/queue-entries.ts#L8-L159).

Before sending, the queue stores that an operation may have reached the server. Network and selected gateway failures retry the same operation ID and body. Only operations never sent can have their base version or item identifier rewritten: [frontend/src/lib/data/write-queue.ts:371–507](frontend/src/lib/data/write-queue.ts#L371-L507), [frontend/src/lib/data/rebase.ts:1–148](frontend/src/lib/data/rebase.ts#L1-L148).

On the server, the authorization check, operation, and stored answer share one transaction. Both applied answers and business rejections are replayed. HTTP errors are not stored. A reused ID with another body or room gives 409: [src/api/idempotency.py:1–76](src/api/idempotency.py#L1-L76), [src/api/ops.py:810–882](src/api/ops.py#L810-L882).

Conflict rules are operation-specific. Stale set operations can succeed when the stored value already matches. Quantity deltas accumulate. An older `item.set_done` request without `base_seq` remains last-writer-wins. Optional due fields also distinguish omission from explicit null: [src/api/ops.py:279–340](src/api/ops.py#L279-L340), [src/api/ops.py:419–433](src/api/ops.py#L419-L433), [src/api/ops.py:600–709](src/api/ops.py#L600-L709).

The view projects local edits over server data. Refresh waits while a write answer is open to avoid counting that write twice. Reconnection pauses sending, rechecks access, refreshes, then resumes the queue. This does not mean that all local offline editing is disabled: [frontend/src/lib/data/room-store.svelte.ts:315–417](frontend/src/lib/data/room-store.svelte.ts#L315-L417), [frontend/src/lib/data/index.ts:820–882](frontend/src/lib/data/index.ts#L820-L882).

### 5. Reminders: implemented foundations, not active phone delivery

Shared item dates and times use the normal operation queue. Python resolves wall-clock times to UTC. The resolver defines daylight-saving gaps and overlaps; the browser does not supply an authoritative instant: [src/reminders/due_schedule.py:1–159](src/reminders/due_schedule.py#L1-L159), [src/reminders/zoned_time.py:1–107](src/reminders/zoned_time.py#L1-L107).

Personal settings and policy APIs exist. They use revisions and a separate replay store. Policy paths check room ownership and device enrollment. They can preserve settings while a saved grant needs resuming; storing a draft is not permission to deliver a notification: [src/api/reminders.py:1–13](src/api/reminders.py#L1-L13), [src/api/reminders.py:350–433](src/api/reminders.py#L350-L433), [src/api/reminder_policies.py:80–199](src/api/reminder_policies.py#L80-L199).

The normal UI hides personal settings through `PERSONAL_REMINDER_SETTINGS_ENABLED = false`. Due views remain available. Phone notifications are documented as not built: [frontend/src/lib/reminders/personal-reminders.ts:1](frontend/src/lib/reminders/personal-reminders.ts#L1), [frontend/src/lib/list/ItemDialog.svelte:208–216](frontend/src/lib/list/ItemDialog.svelte#L208-L216), [docs/due-date-reminders.md:1–7](docs/due-date-reminders.md#L1-L7). Do not count policy storage or preview code as a working delivery service.

### 6. SSE, PWA routes, and deployment

SSE sends sequence numbers, not data rows. The client then fetches the changes feed. Streams reserve bounded capacity, subscribe before their first read, and recheck access at least every 15 seconds. The subscription registry and its 100-stream cap are process-local: [src/api/events.py:34–145](src/api/events.py#L34-L145), [src/live_updates.py:62–129](src/live_updates.py#L62-L129). Room feeds return a full snapshot after first load, a database restore, or missed pruned deletions: [src/api/changes.py:28–55](src/api/changes.py#L28-L55).

The service worker installs a complete versioned app shell and bypasses API requests. Admin and legacy `/app` navigation stay network-only. Automatic takeover and reload are delayed on a page with waiting writes or typed text; explicit Reload is a separate path: [frontend/src/service-worker.ts:1–127](frontend/src/service-worker.ts#L1-L127), [frontend/src/lib/worker-routes.ts:1–15](frontend/src/lib/worker-routes.ts#L1-L15), [frontend/src/lib/service-worker.ts:55–115](frontend/src/lib/service-worker.ts#L55-L115), [frontend/src/lib/service-worker.ts:140–170](frontend/src/lib/service-worker.ts#L140-L170).

FastAPI registers server routes before the SPA fallback. Missing worker and build assets remain real 404s. Legacy `/sw.js` returns a worker-removal script, not the SPA page: [src/svelte_frontend.py:105–164](src/svelte_frontend.py#L105-L164), [src/pwa_routes.py:28–111](src/pwa_routes.py#L28-L111).

Production is documented as one Railway replica, one process, SQLite rollback journaling, and a one-second database lock wait. The code opens one lazy connection with that timeout. These are deliberate limits, not measured capacity failures: [docs/deployment.md:110–135](docs/deployment.md#L110-L135), [src/database_setup.py:18–23](src/database_setup.py#L18-L23), [src/database_setup.py:1145–1198](src/database_setup.py#L1145-L1198).

The deployment script defines format, lint, type, Python, and frontend checks, then a verified production backup before its approved push path. Relevant test selection and the three-engine browser smoke remain separate release requirements: [scripts/deploy_backup.py:46–91](scripts/deploy_backup.py#L46-L91), [docs/deployment.md:138–194](docs/deployment.md#L138-L194). I did not access production or its configuration.

### 7. Duplicated rules and concrete drift

| Finding | Evidence | Interpretation |
|---|---|---|
| Operation fields exist in Python models, TypeScript interfaces, and a partial stored-operation validator. | [src/api/ops.py:163–372](src/api/ops.py#L163-L372); [frontend/src/lib/data/types.ts:84–234](frontend/src/lib/data/types.ts#L84-L234); [frontend/src/lib/data/queue-entries.ts:55–118](frontend/src/lib/data/queue-entries.ts#L55-L118) | Real coordination cost. The validators have different jobs; one cannot simply delete the others. |
| Server emits `invalid_due` and `time_zone_unavailable`, but the frontend `REJECTION_CODES` union omits both. | [src/api/ops.py:623–652](src/api/ops.py#L623-L652); [frontend/src/lib/data/types.ts:249–262](frontend/src/lib/data/types.ts#L249-L262); [frontend/src/lib/data/result.ts:17–24](frontend/src/lib/data/result.ts#L17-L24) | Confirmed type drift. Successful JSON casts do not detect it. Runtime user impact was not tested. |
| Name and text rules span browser convenience checks, server rules, and database protection. Optimistic name matching also approximates Python behavior. | [frontend/src/lib/ui/field-limits.ts:1–20](frontend/src/lib/ui/field-limits.ts#L1-L20); [src/field_limits.py:1–25](src/field_limits.py#L1-L25); [frontend/src/lib/data/overlay.ts:80–123](frontend/src/lib/data/overlay.ts#L80-L123); [src/item_names.py:1–38](src/item_names.py#L1-L38) | Some duplication is necessary for offline feedback and database protection. Cross-runtime Unicode behavior remains a compatibility concern. |
| API version 4 is declared separately in Python and TypeScript. | [src/api/version.py:1–10](src/api/version.py#L1-L10); [frontend/src/lib/data/compat.svelte.ts:8–14](frontend/src/lib/data/compat.svelte.ts#L8-L14); [tests/test_api_version.py:87–91](tests/test_api_version.py#L87-L91) | An explicit equality test exists. This is not evidence that every operation shape has a contract test. |
| Documentation and comments lag behavior. | `Item.name` says lowercase in [frontend/src/lib/data/types.ts:39–44](frontend/src/lib/data/types.ts#L39-L44), while [src/item_names.py:6–14](src/item_names.py#L6-L14) preserves display case. [docs/api-reminders.md:9–16](docs/api-reminders.md#L9-L16) describes visible settings entry points, while the feature flag is false. | Confirmed documentation drift, not a runtime failure. The reminder architecture wording also confuses the cookie secret with the hash stored in SQLite; compare [ARCHITECTURE.md:62–67](ARCHITECTURE.md#L62-L67) with [src/api/reminders.py:296–303](src/api/reminders.py#L296-L303). |

### 8. Three real workflows for later comparison

**Workflow A — Admin invitation → room sign-in → device enrollment and revocation**

1. Admin signs in and issues an invitation.
2. A visitor creates a room. Creation consumes the invitation allowance atomically but grants no room session.
3. The visitor signs in with the new room password.
4. Through the existing API, explicit enrollment creates a device grant. This is not a currently exposed normal UI journey.
5. Room sign-out or password replacement cuts that grant. Signing in again alone does not resume it. Replaying the earlier enrollment must not reactivate it.

Existing tests: [tests/test_room_invitations.py:18–115](tests/test_room_invitations.py#L18-L115), [tests/test_room_invitations.py:161–187](tests/test_room_invitations.py#L161-L187), [tests/test_api_session.py:48–184](tests/test_api_session.py#L48-L184), [tests/test_api_reminders_review.py:157–178](tests/test_api_reminders_review.py#L157-L178).

**Comparison criterion:** preserve separate credentials, concurrent invitation limits, rollback, and explicit grant resume. Measure how many rule and transport definitions a change touches.

**Workflow B — Offline item edit → competing edit → replay, conflict review, and deploy**

1. Device A opens an item and queues an edit offline.
2. Device B changes the item.
3. A reconnects, revalidates access, and sends the original ID and body. A lost reply retries unchanged.
4. A stale conflicting edit is rejected without changing the row. A delayed rejection survives reload for review. A deliberate override is a new change.
5. SSE brings other pages up to date. If a deploy changes the API version, further sending stops until a compatible app version loads; durable operations remain stored.

Existing tests: [tests/test_api_conflicts.py:88–205](tests/test_api_conflicts.py#L88-L205), [tests/test_api_idempotency.py:264–366](tests/test_api_idempotency.py#L264-L366), [browser_tests/test_svelte_offline_conflicts.py:65–170](browser_tests/test_svelte_offline_conflicts.py#L65-L170), [frontend/src/lib/service-worker.test.ts:118–151](frontend/src/lib/service-worker.test.ts#L118-L151), [browser_tests/test_svelte_service_worker.py:374–405](browser_tests/test_svelte_service_worker.py#L374-L405).

**Comparison criterion:** no duplicate application, lost durable operation, silent overwrite, or forced automatic reload of a busy page. Count the changes needed across queue, model, response, projection, and migration code. This combined sequence was not executed here.

**Workflow C — Public list edit → room member resets the link**

1. A visitor opens one list without room access.
2. The visitor edits or queues an item change using that link.
3. A room member resets the link.
4. The old token cannot read, write, or retrieve a previously stored operation answer. Its stream reports revocation after rechecking access. The old queue is not transferred automatically to the replacement token.

Existing tests: [tests/test_api_share.py:100–142](tests/test_api_share.py#L100-L142), [tests/test_api_share.py:400–421](tests/test_api_share.py#L400-L421), [tests/test_api_share.py:490–515](tests/test_api_share.py#L490-L515). Client adaptation: [frontend/src/lib/data/share.ts:1–107](frontend/src/lib/data/share.ts#L1-L107). Discard-only handling after reset is documented in [docs/offline-viewing.md:64–71](docs/offline-viewing.md#L64-L71).

**Comparison criterion:** no other-list access, room metadata leak, or replay that bypasses revocation. Preserve separation of room and share queues.

### 9. Tests and current check status

**Current execution status:** no application tests, format checks, lint checks, type checks, builds, browser checks, or deployment checks were run. No passing result is claimed. The required `subagent doctor` diagnostic ran successfully; it is not an application quality check.

Source inspection found these distinct layers:

- **API and database:** room/admin cookies, share scope, invitation races, operation replay, stale edits, migration rollback, and name-key collisions. Examples include `test_replay_returns_the_stored_bytes_without_a_second_write` in [tests/test_api_idempotency.py:264–282](tests/test_api_idempotency.py#L264-L282), and migration failure tests in [tests/test_migrations.py:63–121](tests/test_migrations.py#L63-L121).
- **Frontend unit tests:** fake IndexedDB checks queue isolation and atomic rejection settlement; fake streams check refresh and reconnect behavior: [frontend/src/lib/data/queue-storage.test.ts:75–140](frontend/src/lib/data/queue-storage.test.ts#L75-L140), [frontend/src/lib/data/events.test.ts:46–115](frontend/src/lib/data/events.test.ts#L46-L115).
- **Browser tests:** real UI conflict journeys and actual service-worker cache behavior. Some worker-upgrade tests use modified build copies, not a real Railway deploy: [browser_tests/test_svelte_service_worker.py:157–194](browser_tests/test_svelte_service_worker.py#L157-L194), [browser_tests/test_svelte_service_worker.py:449–493](browser_tests/test_svelte_service_worker.py#L449-L493).

Configured checks include Ruff, pytest, and `ty` for `src/`; frontend lint, Svelte/TypeScript checks, Vitest, and a Vite build. See [pyproject.toml:30–80](pyproject.toml#L30-L80), [frontend/package.json:6–15](frontend/package.json#L6-L15), and [scripts/deploy_backup.py:73–91](scripts/deploy_backup.py#L73-L91). Some Python route tests need a frontend build or they skip. Personal-settings browser checks remain deliberately paused: [docs/testing.md:25–30](docs/testing.md#L25-L30), [docs/testing.md:67–75](docs/testing.md#L67-L75).

Test presence does not prove passing checks, assertion quality, or complete coverage. This report does not repeat the separate test-removal or lint-rule audits.

## Arguments for and against

**For retaining the current stack:**

- It matches the documented small-group, single-instance scope.
- Authorization and mutation can share a short transaction.
- Retry, conflict, migration, and installed-app compatibility rules already exist in code and tests.
- Keeping the API and Svelte avoids changing several independent systems at once.

**Against treating the current stack as easy to change:**

- Rules cross Python, SQL, TypeScript, browser storage, and installed app versions.
- Broad dictionaries and `Any` weaken otherwise useful static types.
- Hand-maintained types have already drifted from server behavior.
- Database triggers and Python-backed SQLite functions make migrations an important part of application behavior.
- Process-local locks, rate limits, and stream subscriptions require the current one-process operating model.

These are costs to compare. They do not show that TypeScript, Effect, another Python framework, or another frontend would remove them. A generated schema could reduce declaration drift; it would not replace authorization, transaction, migration, or browser behavior tests.

## Recommendation

1. Keep the current stack and API as the reference implementation for the remaining Phase 1 research.
2. Compare alternatives against the three workflows above, not file counts or framework examples.
3. Prefer a later, explicitly approved small trial over a rewrite. Measure change time, touched contract definitions, new compatibility branches, checks required, and defects found. Keep behavior and SQLite fixed where possible.
4. Give the confirmed rejection-code and documentation drift to the existing review owners. They are candidates for bounded follow-up, not permission to edit now.
5. Preserve the existing release gates. This research adds no staging, rehearsal, or manual phone-testing requirement.

## Unknowns

- Checkout identity was not independently verified against the supplied baseline.
- Current test, build, lint, and type results are unknown. No historical passing result was substituted.
- Production lock contention, SSE reconnect rates, storage eviction, and device behavior were not measured.
- The runtime effect of the missing rejection codes was not reproduced. The type mismatch itself is directly visible.
- The cost of generated contracts or runtime response validation is unmeasured.
- No claim is made about active phone-notification delivery; the normal settings UI is disabled and delivery remains documented as pending.
- Live coordination with test-review owners was not permitted by this session's tool contract. Coordination here is limited to the supplied task snapshots and this handoff.

## Handoff

**To the runner and reviewer:** this is the full source-level research report for `lr-ngj`. Independently review it before the runner treats the bead as accepted. Preserve the baseline qualification and unrun-check status. No files, Beads records, version-control state, servers, or agents were changed or started. Only the required subagent diagnostic was used.

**To the test-review owners, by owner relay:** the supplied snapshot assigns Python-to-TypeScript contract work to `lr-347.4.3` and lint/tool analysis to `lr-347.4.4`. Send the two missing rejection codes, response cast, and three operation-shape locations to `lr-347.4.3`. Leave strict-flag error counts, code sketches, mutation work, and test-removal recommendations with those tasks. Snapshot creator fields do not establish a current active claimant.

**To the remaining stack research:** use these workflows and preserved guarantees as common inputs. Separate observed drift from proposed gains. A recommendation to keep Python, keep Svelte, adopt only a small tool, or stop remains valid. Implementation, dependency changes, integration, and deployment remain outside this approval.
