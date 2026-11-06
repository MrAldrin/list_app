# Code Context

## Files Retrieved

Repository source was read at the frozen operation below; no source or graph was changed. The relevant revision-specific source was read using `jj file show -r groups` rather than switching workspaces.

1. `plans/jj-history-review.md` (lines 212–256) — current Owner follow-up authority: exact candidates, conditional `reminders-s2` bookmark-removal permission, and explicit no-rebase/no-remote-delete limits.
2. `AGENTS.md` (lines 31–74) and `docs/scope.md` (lines 29–44) — accepted `integration` baseline and approval gates for bookmark/history changes.
3. `ARCHITECTURE.md` (lines 106–111) — current decision for mobile bottom-bar behavior.
4. `plans/named-item-groups.md` (lines 12, 16–63, 86–93) — planned groups semantics/dependencies; its progress still says implementation and verification incomplete and its state cites `rlzvuowp`.
5. `plans/backlog.md` (lines 33–39) — groups remain a parked feature, not accepted/deploy-ready work.
6. `groups:plans/batches/groups-delivery.md` (lines 17–26, retrieved from `groups`) — older delivery/review/check record, not present in the current integration worktree.
7. `groups:src/api/item_groups.py` (lines 1–25, 106–194); `groups:src/database_setup.py` (lines 876–986, 1034–1052); `groups:frontend/src/lib/data/types.ts` (lines 39–85, 152–157, 245–256); `groups:frontend/src/lib/data/index.ts` (lines 535–598) — backend, schema, client/queue, and UI entry points in the parked source.
8. `integration:src/database_setup.py` (lines 798–944, 1124–1143) — current accepted schema-migration sequence, which makes the parked groups migration numbers incompatible as-is.
9. `frontend/src/lib/list/AddItem.svelte` (lines 1–4, 32–50, 149–155), `frontend/src/lib/ui/BottomBar.svelte` (lines 1–7, 18–40, 47–57), and `frontend/src/lib/room/RoomLists.svelte` (lines 1–8, 40–48, 107–137) — behavior currently implemented on the accepted Svelte line.
10. `browser_tests/test_svelte_items.py` (lines 65–110) and `browser_tests/test_svelte_bottom_bar.py` (lines 1–49) — tests of the current usual-item popup and bottom-bar behavior.
11. `plans/batches/reminders-s2.md` (lines 92–100, 125–128) — old S2 workspace/ownership record and its statement that no active writer remained. The live workspace inventory was separately refreshed at the frozen operation.

## Key Code

### Frozen graph and exact refs

Every `jj` command used this immutable operation:

`dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d`

At that snapshot:

| Candidate | Exact tip (full change ID / full commit ID) | Merge base and unique source relative to accepted `integration` | Classification / recommendation |
|---|---|---|---|
| `groups` | `qwywttmonrutzsyrkrupkmykpmpmrlzy` / `2a46f1a4b3d4d588c14349e9f6bd733e3d50bb34` | Common base with `integration` and `main`: `sumkxkqqtnssstkruyqouktmyllyssoz` / `391b36fd141630206fb38978ac52fcd9334a89dc`. Five unique revisions; base-to-tip feature delta touches 57 files (+2,942/−84). | Meaningful parked feature source, not a disposable leaf. Keep the exact original bookmark/tree; do not rebase, copy/abandon, or repair it. Refresh its stale plan and create a separately authorized current-baseline implementation/reconciliation plan before any future work. |
| `reminders-s2` | `wlwznqlymtxmxynrrwmorpvqpzmnlnly` / `e50da7ce0a5456159f8206513c820e7180abbb8e` | The merge base with `main` is the tip itself; `reminders-s2` minus `ancestors(main)` is empty (zero unique commits). | Exact tip is included in `main`. This is the one conditional local-bookmark cleanup candidate, not a source deletion. Hold until the live-name dependency check and fresh review are complete; record the exact IDs and preserve the commit. |
| `usual-items-redesign@origin` (cached tracking ref only) | `kvwywrsxpktluzqkmzroyzuoqstkspvy` / `3d1b2711825ef6e9da08d10bf90a76f54e1c8c2f` | Common base with `integration`/`main`: `mzwwpxmnwvkvymoxopwtqrokwmruynro` / `a0185e1af6ff6a7c4ee6ffb130e8e6bcf977c519`. One unique commit, also not an ancestor of `main`. | Not literally merged. The behavior is implemented by the current Svelte Add/Search popup and tested there. Treat as a stale remote-name cleanup proposal, not evidence of missing product code. Do not delete the cache or remote branch without the required itemized owner decision. |
| `wave2-bottom-bar@origin` (cached tracking ref only) | `vvsnkwnmstlruwxvtslvlqosuoxuwuyv` / `85c93c3428aca4daed9727e624ca176eb3cf3e22` | Same common base: `mzwwpxmnwvkvymoxopwtqrokwmruynro` / `a0185e1af6ff6a7c4ee6ffb130e8e6bcf977c519`. One unique commit, also not an ancestor of `main`. | Not literally merged. The current Svelte line has a fixed bottom bar, keyboard lift, list/room actions, top toasts, and browser coverage. Treat as a stale remote-name cleanup proposal; preserve until an itemized owner decision. |
| `integration@origin` (cached tracking ref) | `krnplyqystqvuovpqlssroulzlxwpyxp` / `ddd687e25485c4707ad1ee7952da296e8987531f` | It is the common ancestor of local `integration`; local `integration` has 136 commits not in that cached tip. Local `integration` contains `main` and is 22 commits ahead of `main`; `main` has zero commits absent from local `integration`. | Not obsolete just because it is behind. It records a cached published/tracking position, not the current local accepted baseline. Keep it; do not delete/fetch/push or infer current server state from it. |

The exact five `groups`-only revisions relative to `integration`, oldest to newest, are:

- `zpuounkqxrkrrrqqltwwqwztvpvxlvwr` / `b00f98c5b4d4039c542054695e0b402ab64fc6e1` — delivery record.
- `xxktorwzrmmypxnxrxuvllpzolwnkmnn` / `08bd81c3286edd2fba0b28e8a174a164915a7257` — persist room catalog and retry-safe adds.
- `mmxrtpyxzoumzookzzvmzpupnmrwxzto` / `86685224694630f905b113b72d346345c0cea81b` — verification-record update.
- `rlzvuowpnkzzyymtytrrpmtnusykxrtq` / `bc9a5f1e820156920f88a9e2d37e85568064ad49` — phone group-control/UI and test updates.
- `qwywttmonrutzsyrkrupkmykpmpmrlzy` / `2a46f1a4b3d4d588c14349e9f6bd733e3d50bb34` — migration test/options layout fix.

The branch contains meaningful behavior, not just a plan: room-authorized online group create/update/delete, ordered names, a room group catalog in the change feed/snapshot, `item.add_if_absent`, queue replay with optimistic-UID remapping, partial results, and group editor/add UI. The main test seams are `tests/test_api_item_groups.py`, `tests/test_api_item_ops.py`, `tests/test_database_setup.py`, `frontend/src/lib/data/offline-integration.test.ts`, `frontend/src/lib/data/rebase.test.ts`, and `browser_tests/test_svelte_item_groups.py`. That matches the plan’s important semantics: checked matches are skipped, not restored; server checks are needed for races/replay; group members are separate writes and can partially fail. The source is feature work still outside accepted `main`/`integration`.

**Compatibility blocker:** the parked branch adds `_migration_15_named_item_groups` and `_migration_16_item_group_tombstone_retention` (`groups:src/database_setup.py:876–986`). Current accepted `integration:src/database_setup.py` already uses migration 15 for due time/zone, 16 for private reminders, 17 for due-cycle start, and 18 for private policies (`src/database_setup.py:798–944`, `_migrations` at 1124–1143). Migration numbers cannot be rewritten/reused; group storage must be reconciled as new migration(s) after 18, with the current `database_crud`, feed/change, item-name-key and operation contracts. The feature is not safe to replay wholesale onto today’s tree. The old batch record reports independent review and 1,481 Python / 660 frontend / 378 browser tests, but those receipts refer to the older delivered source (`xxktorwz`, recorded there as commit `5702e7ce`). The current `groups` tip has later `rlzvu` and `qwy` source/test changes after the verification-record change. No current-baseline check or fresh review was run in this scout. The backlog and current plan still call the feature parked/incomplete; keep it that way pending a new approved implementation/review.

**Usual items:** the cached commit’s own change is limited to `frontend/src/lib/list/AddItem.svelte`, `browser_tests/test_svelte_items.py`, `docs/adding-items.md`, and `plans/backlog.md` (47 insertions/79 deletions). It is not an ancestor of the current baseline. The current Svelte component now uses `usualItemSuggestions`, shows the `Usual items` listbox only when the blank field is focused, and shares keyboard/touch suggestion rules (`frontend/src/lib/list/AddItem.svelte:32–50, 149–155`); the browser test explicitly covers blank-focus, keyboard and touch (`browser_tests/test_svelte_items.py:86–110`). This is a behavioral replacement, not proof that the origin commit was merged.

**Bottom bar:** the cached commit changed 12 paths, including `BottomBar.svelte`, `ListView.svelte`, `RoomLists.svelte`, toast behavior, docs and `test_svelte_bottom_bar.py` (185 insertions/67 deletions). It is not an ancestor of current `main`/`integration`. The current Svelte `BottomBar` is fixed, reserves spacer height, and raises above iPhone keyboard using `visualViewport`; list and room pages place their principal add actions there, while architecture puts toasts at the top (`frontend/src/lib/ui/BottomBar.svelte:1–7, 18–57`, `frontend/src/lib/room/RoomLists.svelte:107–137`, `ARCHITECTURE.md:106–111`). Current browser coverage asserts bottom placement and upward-opening suggestions (`browser_tests/test_svelte_bottom_bar.py:1–49`). Again, equivalent behavior exists without literal ancestry.

### `reminders-s2` name-dependency check

The exact-tip ancestry check passes: `e50da7ce…` is the latest common ancestor with `main`, and `reminders-s2 ~ ancestors(main)` yields zero commits. The frozen bookmark/workspace snapshot has no `tmp-reminders-s2` workspace; `jj op show` reports the current operation as a `test-runtime-docs` rebase, and `scripts/` contains no `reminders-s2` command match. The old S2 plan also records the S2 entry as cleaned up and no active writer at lines 125–128. However, the workspace list still includes a Lead-owned `tmp-reminder-delivery` aggregate. No process/session inventory was available in the allowed tools, so this scout cannot certify that no live shell or peer command uses the symbolic bookmark name. This criterion is therefore **not fully attested**; have the Lead check live peers/commands before removing the local bookmark. Historical plan/batch mentions are records, not active-name dependencies.

### Remote-reference interpretation

`usual-items-redesign@origin`, `wave2-bottom-bar@origin`, and `integration@origin` are only cached local tracking refs in this snapshot. No fetch or remote command was made; whether those names currently exist on the server is unknown. `integration@origin` being behind is expected evidence of a local accepted line ahead of its last published/tracked point: local `integration` is `pqkxvymsplot` / `32ba4d4035e188b35576f796f64e104499bc4155`, local `main` is `xsqznkopupwtxwtwnwosrlksryoxzpmw` / `250c17b669605cea59bd671ba7e9e49ee3dcbce6`, and `main` is an ancestor of local `integration`. This follows the project rule that local `integration` is the accepted baseline and may be ahead of production `main`; it does **not** authorize moving `integration`, deleting a cached ref, or altering a remote branch.

### Read-only command evidence

All commands below used the exact frozen `--at-op` and `--ignore-working-copy` flags. No fetch, remote, app, environment/secret, test, or mutation command was run.

```sh
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d op show
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d bookmark list --all-remotes
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d workspace list
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'reminders-s2 ~ ancestors(main)' -T 'change_id.short() ++ " " ++ commit_id ++ "\n"' --no-graph
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'heads(ancestors(reminders-s2) & ancestors(main))' -T 'change_id ++ " " ++ commit_id ++ "\n"' --no-graph
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'ancestors(groups) ~ ancestors(integration)' -T 'change_id ++ " " ++ commit_id ++ " " ++ description.first_line() ++ "\n"' --no-graph
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'heads(ancestors(groups) & ancestors(integration))' -T 'change_id ++ " " ++ commit_id ++ "\n"' --no-graph
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d diff --from sumkxkqqtnss --to groups --stat
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d show usual-items-redesign@origin --stat
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d show wave2-bottom-bar@origin --stat
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'heads(ancestors(integration) & ancestors(integration@origin))' -T 'change_id ++ " " ++ commit_id ++ "\n"' --no-graph
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'ancestors(integration) ~ ancestors(integration@origin)' -T 'commit_id ++ "\n"' --no-graph | wc -l
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'ancestors(integration) ~ ancestors(main)' -T 'commit_id ++ "\n"' --no-graph | wc -l
jj --ignore-working-copy --at-op=dcbea95d4cd7b5a7c0a13003e6a3d83320c6d9ac0acafa127bf084f76f9718152bab75bbe5687085196accea1b78628609bfb8dbdd67bdf94b5b7050fe451e7d log -r 'conflicts() & (ancestors(groups) | ancestors(reminders-s2) | ancestors(usual-items-redesign@origin) | ancestors(wave2-bottom-bar@origin) | ancestors(integration) | ancestors(main))' -T 'change_id ++ " " ++ commit_id ++ "\n"' --no-graph
```

The filtered conflict and divergence revsets both returned no revisions in the named candidate/main/integration histories. This does not classify unrelated graph-wide divergences outside this bounded task.

## Architecture

This was a read-only ancestry/code scout, not an implementation or acceptance review. The project boundary remains FastAPI/SQLite plus Svelte; named groups add new server-owned room data and offline-queue semantics, whereas usual-item suggestions and bottom-bar layout are frontend behavior already represented on the accepted Svelte line. For groups, the database migration overlap and API/feed/client integration seams require a current-baseline port and fresh review, not rewriting the parked branch. For the three `@origin` refs, a tracking bookmark is a local cached pointer distinct from the remote-server branch; remote state was not queried.

**Model evidence:** no scout-session host metadata for selected/effective model or reasoning tier was exposed by the available tools. The plan records the parent Conductor selection as GPT-6.1 Sol/high, but that does not attest this scout’s effective model. Scout tier is unverified/unsupported.

## Start Here

Open `plans/jj-history-review.md` at the Owner follow-up (lines 212–256) first: it defines exactly which local cleanup is conditionally permitted and forbids converting these findings into a remote delete or feature-history rewrite. For group continuation, then open `plans/named-item-groups.md` and compare its parked source reference with the exact `groups` head and the current integration migration sequence.
