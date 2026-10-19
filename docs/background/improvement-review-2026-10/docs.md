# ListR documentation audit

Scope: README.md, ARCHITECTURE.md, AGENTS.md, frontend/README.md, docs/*.md (16),
docs/background/*.md (19), plans/*.md (6). Checked against src/, frontend/src/,
browser_tests/, tests/, scripts/, Dockerfile and pyproject.toml. Read-only: nothing
in the repo was edited or committed.

Method notes:
- Markdown links: 218 checked (relative paths and `#anchors`). 0 broken.
- Backticked file paths: checked for existence. Real breaks listed below.
- Helper scripts (not in repo): `<scratchpad>/linkcheck.py`, `<scratchpad>/pathcheck.py`.

---

## 1. Ranked fixes

Effort: S = under 15 min, M = 15-60 min, L = more than an hour or needs a decision.
"Decision" means the owner must choose before the fix.

### Wrong facts (fix first)

1. **docs/api.md:149, 243, 282. Password limit is wrong.**
   Text says "Passwords are at most 1,024 characters (else 422)."
   The real rule is at api.md:91-94: 4 characters minimum, 72 UTF-8 bytes maximum.
   Code: `src/database_crud.py:1011-1029` enforces 72 bytes. `src/field_limits.py:13`
   sets the 1,024-character cap, which the 72-byte rule always hits first.
   Fix: delete the three 1,024 sentences. Keep the rule once, at api.md:87-94.
   Why: a reader gets two limits. Effort: S.

2. **docs/home-screen-installation.md:55-59 and docs/deployment.md:133-135. Says plain HTTP stores the room token in localStorage.**
   Code: the room token lives only in cookies. The frontend uses localStorage
   only for the theme (`frontend/src/lib/ui/theme.ts`), per-list view settings
   (`frontend/src/lib/list/items.ts`) and a stale-build timestamp
   (`frontend/src/lib/stale-build.ts`). docs/api.md:118-120 and ARCHITECTURE.md:56-57
   already say "cookie, no localStorage fallback".
   Fix: delete the localStorage sentences. Say "plain HTTP uses the same cookies
   without `Secure` (api.md:113-120)". Also delete home-screen:58-59 (the
   "old localStorage tokens move" line, which describes code that no longer exists).
   Why: wrong security and testing facts. Effort: S.

3. **docs/public-sharing.md:56. Test file does not exist.**
   `test_public_sharing.py` is not in `browser_tests/`. The real file is
   `browser_tests/test_svelte_share.py`.
   Fix: replace the name. Effort: S.

4. **ARCHITECTURE.md:6-7 vs AGENTS.md:16 and docs/deployment.md:140. User count.**
   ARCHITECTURE says "up to four simultaneous users". AGENTS and deployment say
   "about five users".
   Fix: pick one number. The owner decides. Effort: S (decision).

5. **plans/backlog.md:21. Step 5.1 instruction is already done.**
   The clause "Step 5.1 must use a different worker URL (such as `/service-worker.js`)"
   is already true: `frontend/src/service-worker.ts` exists, and
   docs/home-screen-installation.md:49 says the app worker is `/service-worker.js`.
   Fix: keep only the "keep `/sw.js` until 2027-04-06" rule. Effort: S.

6. **plans/backlog.md:41. "sign-in rate limiting" listed as a future user-profile use.**
   The limit already exists: `src/sign_in_limiter.py`, `src/api/sign_in_limit.py`,
   and docs/api.md:103-111.
   Fix: remove that phrase. Effort: S.

7. **plans/backlog.md:45. "Add timestamps and change versions" is partly done.**
   Code has `change_seq`, `changed_seq` (migrations 4, 8), `added_at` (migration 10)
   and `completed_at`. Only "audit history" is still open.
   Fix: shorten the item to audit history. Effort: S.

8. **plans/backlog.md:43. Completed-work note inside an open item.**
   "(Splitting `src/main.py` is done: ...)" is a log entry.
   Fix: delete the parenthetical. Effort: S.

9. **plans/test-suite-speed.md:79. Stale bullet.**
   The first Priority 4 bullet ("Remove unnecessary valid-hash creation ... in
   `tests/test_password_hashes.py`") is already done, per
   docs/background/codebase-cleanup.md:156.
   Fix: delete the bullet. Also see items 22 and 23 below. Effort: S.

10. **docs/browser-testing.md:74-76. Garbled sentence.**
    Unbalanced parenthesis and a run-on list: "...stale actions, hide-done), and toasts...".
    Fix: rewrite as two short sentences. Effort: S.

11. **docs/deployment.md:84-86 and 279. Garbled long lines.**
    Two sentences are joined on one line in a way that reads wrong.
    Fix: reflow and split. Effort: S.

### Quality rules (AGENTS.md:57-63)

12. **docs/deployment.md (283 lines).** Mixes current procedure with one-time history:
    - Lines 106-108: "The first deploy of the Svelte version moves a production database from version 2 to 4."
    - Lines 270-283: "Rolling back the Svelte deploy (database version 2 to 4)". This runbook
      needs the NiceGUI code and `NICEGUI_STORAGE_SECRET`, which no longer exist in `src/`.
    - Lines 85-90: pre-Svelte and NiceGUI notes.
    Fix: move history to docs/background/ and keep the generic restore steps (lines 249-268).
    Decision: owner confirms that the NiceGUI rollback is no longer needed. Effort: M.

13. **docs/api.md (486 lines).** Contract reference, far over one screen.
    Also stacked caveats at lines 91-94 (password rule with a sign-in exception) and
    106-111 (sign-in limit).
    Problem: AGENTS says "split detail to docs/background/", but background must not be
    the primary source (AGENTS.md:42). There is no home for split reference material.
    Decision: keep as a reference exception, or create a reference folder (for example
    `docs/reference/`). Effort: L (decision first).

14. **docs/deployment.md (283 lines) also covers two different topics.** Same fix
    family as item 12 and the rollback question. A runbook (checklist, restore) and a
    config table are separate things. Effort: L.

15. **README.md (152 lines).** Three things do not belong in an app intro:
    - Lines 123-135, "Allium pilot (optional)": agent tooling. Move to `docs/` or `plans/`.
    - Lines 39-57, "New jj workspace": developer workflow. Move to `docs/development.md`.
      AGENTS.md:13 links to `README.md#new-jj-workspace`, so update that link too.
    - Line 113: "Real-browser sharing tests" should read "Real-browser tests". The suite covers all browser tests.
    Effort: M.

16. **README.md:137-149 (Documentation list) is missing links:** `docs/offline-viewing.md`
    (a headline feature), `docs/change-tracking.md`, and `AGENTS.md`. Effort: S.

17. **ARCHITECTURE.md (131 lines).**
    - Lines 124-131 ("Evolution and documentation") repeat AGENTS.md:38-55. Replace with one
      line that points to AGENTS.md.
    - Lines 25-29 and 115-118 repeat offline rules in `docs/offline-viewing.md`. Keep one
      sentence each and link.
    - Lines 5-7 still call the app an "MVP". The app is live. Wording only.
    Effort: M.

18. **Manual-check rule repeated in 7 files.** The rule lives in AGENTS.md:19-20 (owner).
    These copies should become one link each:
    - docs/deployment.md:140-143, 159-160
    - docs/home-screen-installation.md:81-83
    - docs/local-network-testing.md:3-6
    - docs/android-emulator-testing.md:5-6
    - docs/browser-testing.md:21-23
    - plans/test-suite-speed.md:87-89
    - plans/staging-environment.md:8-10
    Effort: S.

19. **Backup status repeated.** AGENTS.md:16, docs/deployment.md:222-223 and
    plans/backup-options.md:5-7 all say "backup on each deploy, no recurring backup".
    Owner: docs/deployment.md backup section. The plan should link there. Effort: S.

20. **Browser test command repeated.** README.md:113-118 and docs/browser-testing.md:9-13 are
    identical. Keep it in browser-testing.md; the README gets one line and a link. Effort: S.

21. **Python checks differ.** AGENTS.md:101-116 lists `ruff format`, `ruff check --fix`,
    `ty check` and `pytest`. README.md:96-100 omits `ty check` and the format/fix steps.
    The README is the newcomer's first stop. Make them match, or link to AGENTS. Effort: S.

22. **plans/test-suite-speed.md:39 and 47-49.** "on this branch; no offline-branch
    integration" is stale branch language. Lines 47-49 (the discarded offline experiment)
    are history. Move 47-49 to docs/background/test-suite-speed.md or offline-findings.md. Effort: S.

23. **plans/advanced_sharing.md has no Progress section.** AGENTS.md:34 requires one at the
    bottom of every plan. Add one with "No work started" or similar. Effort: S.

24. **Dated history in top-level docs (move or delete):**
    - docs/checked-item-visibility.md:18-22: migration history ("Existing zero counters are reset...",
      "Items already checked before this feature..."). Move to background; keep a one-line caveat.
    - docs/public-sharing.md:46-52: "Rollout and verification" is one-time rollout text.
      Keep the "rolling back re-exposes slug routes" warning. Move the rest.
    - docs/room-invitations.md:15: "No additional database migration is needed for this cleanup."
      That is a change-log sentence. Delete.
    - docs/api.md:436: "Answers stored before this was added have no `changed_seq`." History. Shorten or delete.
    Effort: S each.

25. **Environment-specific details in docs/local-network-testing.md:**
    - Line 39: heading "Svelte prototype". The app is live. Rename to "Svelte app".
    - Lines 17-23, 36, 68: private Tailscale IPs and hostname. These go stale when a device changes.
      Keep the steps generic and put device values in a local note.
    Effort: S.

26. **docs/browser-testing.md:20.** "On this laptop WebKit needed `sudo apt-get install libavif16`."
    Machine-specific. Move to docs/background/browser-testing.md. Effort: S.

27. **docs/room-invitations.md:11-12 and 35.** Stacked caveats (admin, privacy, logs). Keep one
    sentence on who can see what. Effort: S.

28. **Broken pointer in background.** docs/background/fixes-deployment-2026-10-06.md:5 links to
    `plans/backlog.md#manual-checks`. That section says "None." The link no longer means what it
    says. Delete the line or retarget. Effort: S.

### Plans and backlog status

29. **plans/staging-environment.md. Superseded; should be retired (decision).**
    - Lines 8-11 say "not planned (2026-10-18)... Kept for reference only."
    - AGENTS.md:17 says "Do not add ... staging".
    - Lines 28-29 use `jj bookmark set staging`. AGENTS.md:69 says there are no other shared bookmarks.
    - Seven boxes are still open (lines 38-47), which contradicts "not planned".
    - Dated log lines 56-57.
    Fix: move the "no staging" decision to `plans/backlog.md` Ideas (or background), then delete the
    plan in its own change, with approval. Effort: M (decision).

30. **plans/backup-options.md. Keep, but link instead of repeating.** Line 5 repeats deployment.md. Effort: S.

---

## 2. Facts repeated across files

Owner = the file that should hold the fact. Other files should link to it.

| Fact | Copies (file:line) | Owner |
|---|---|---|
| Password limits | api.md:87-94 (4 chars, 72 bytes); api.md:149, 243, 282 (1,024 chars, wrong); ARCHITECTURE.md:53; backlog.md:35; code: database_crud.py:1011-1029, field_limits.py:12-13 | api.md:87-94 |
| Token storage on plain HTTP | api.md:113-120 (cookie, no localStorage); home-screen-installation.md:55-59 (localStorage, wrong); deployment.md:133-135 (localStorage, wrong); ARCHITECTURE.md:56-57 | api.md (names) and ARCHITECTURE.md (decision: JS never sees the token) |
| Admin login never grants room access | ARCHITECTURE.md:43-47; api.md:208-210; room-invitations.md:11; public-sharing.md:9-10; home-screen-installation.md:62-63 | ARCHITECTURE.md (decision) |
| Room password change revokes tokens, not share links | ARCHITECTURE.md:52; api.md:123, 144-145, 198; public-sharing.md:22-23; home-screen-installation.md:60-61 | api.md:123 and public-sharing.md:22-23 |
| Share-link behavior | ARCHITECTURE.md:33-38; public-sharing.md:5-27; api.md:153-198 | public-sharing.md (behavior); api.md (endpoints) |
| Invitations: 7 days, no room access | ARCHITECTURE.md:58-64; room-invitations.md:9-15, 19-25; api.md:264-283 | room-invitations.md |
| Field limits (100 / 30 / 1000 / 1000 items / 100 lists / 50 tags) | item-writes.md:41-49; api.md:443-444 | api.md rejection table (item-writes links to it) |
| What counts as an "add" | item-sorting.md:21-22; item-writes.md:34-35; api.md:400-406 | api.md:400-406 |
| Offline rules | ARCHITECTURE.md:25-29, 115-118; offline-viewing.md | offline-viewing.md |
| Manual device checks only for very high risk | AGENTS.md:19-20; 7 copies (item 18) | AGENTS.md |
| Backup before deploy | AGENTS.md:16; deployment.md:162-187, 222-223; backup-options.md:5-7 | deployment.md |
| Browser test command | README.md:113-118; browser-testing.md:9-13 | browser-testing.md |
| Two-server development | README.md:84-88; frontend/README.md:19-27 | frontend/README.md (frontend steps) |
| Python quality checks | AGENTS.md:101-116; README.md:96-100 | AGENTS.md (agent rules); README should match |
| Doc lifecycle policy | AGENTS.md:38-55; ARCHITECTURE.md:124-131 | AGENTS.md |
| Users: "four" vs "five" vs "4" | ARCHITECTURE.md:6-7 (four); AGENTS.md:16 (five); deployment.md:140 (five); codebase-cleanup.md:9,152 (4, background) | one number, see item 4 |
| `/sw.js` kill switch | ARCHITECTURE.md:119-122; home-screen-installation.md (worker section); backlog.md:21; decision 159 | home-screen-installation.md (behavior); backlog keeps the date |
| Sign-in rate limit | api.md:103-111 (owner); ARCHITECTURE.md:53-54 (links to api.md, good pattern); backlog.md:41 (stale); decision 144 in svelte-frontend-rewrite.md:219 says "rate limiting (skipped)" | api.md; decision 144 is dated history |

Pattern to copy: ARCHITECTURE.md:53-54 states the rule in one line and links to docs/api.md.

---

## 3. Stale content (claims that do not match code or docs)

- **S1. localStorage for room tokens.** Fix item 2.
- **S2. "1,024 characters" password rule.** Fix item 1.
- **S3. `test_public_sharing.py`.** Fix item 3.
- **S4. Step 5.1 worker URL.** Fix item 5.
- **S5. Backlog "sign-in rate limiting".** Fix item 6.
- **S6. Backlog "add timestamps and change versions".** Fix item 7.
- **S7. NiceGUI rollback runbook** (docs/deployment.md:270-283). Needs code that no longer exists. Fix item 12.
- **S8. Deployment history** (docs/deployment.md:106-108). Fix item 12.
- **S9. Plan stale bullet** (plans/test-suite-speed.md:79). Fix item 9.
- **S10. Plan branch language** (plans/test-suite-speed.md:39). Fix item 22.
- **S11. Superseded staging plan.** Fix item 29.
- **S12. Backlog link to manual checks** (background/fixes-deployment:5, target says "None."). Fix item 28.
- **S13. Code comment:** `frontend/src/lib/ui/theme.ts:8` says "The localStorage key NiceGUI uses". Code, not docs. Reword when someone touches the file.
- **S14. Background jj IDs and "Gate V" jargon** (docs/background/offline-viewing-validation.md:9, 12). History only. No fix needed.
- **S15. Background decision 144** (svelte-frontend-rewrite.md:219) says "rate limiting (skipped)". The code now has rate limiting. The decision is dated 2026-10-06, so it is history. Add a one-line note, or leave.

Checked and correct (no action): deploy script behavior and flags (scripts/deploy_backup.py); `serve_svelte_local.py` options; `DB_BACKUP_PATH` default; `REQUIRE_FRONTEND_BUILD`; `APP_RELOAD` in `.env.example`; busy timeout 1 s (`src/database_setup.py:18`); cookie names and admin cookie (14 days); sign-in limit numbers (10 per room, 10 admin); body limit 64 KB; migration numbers cited in docs (2, 4, 6, 8, 9, 10); sort labels (`frontend/src/lib/data/order.ts:55-62`); `UNDO_DURATION` 5 s; the frontend npm scripts in frontend/README.md:45; Node 24 and Python 3.13.

---

## 4. Broken or outdated links

- Markdown links: 0 broken (218 checked, anchors included).
- Prose file references broken in top-level docs: docs/public-sharing.md:56 (fix item 3).
- Prose references to deleted files in background docs (history, acceptable, no action):
  - docs/background/nicegui-test-retirement.md (many `test_*.py` names)
  - docs/background/browser-test-port-map.md
  - docs/background/codebase-cleanup.md:35, 64, 76, 78 (`src/item_service.py`, `src/lib/index.ts`, `browser_tests/test_svelte_install.py`)
  - docs/background/home-screen-installation.md:39 (`src/room_access.py`)
  - docs/background/offline-findings.md:27-28 (`plans/offline-readonly.md`, `plans/offline-options.md`, `plans/iphone-installed-offline-acceptance.md`)
- Outdated intent link: docs/background/fixes-deployment-2026-10-06.md:5 (fix item 28).
- Orphan background docs (no incoming link): docs/background/deploy-rehearsal-2026-10-06.md and docs/background/offline-viewing-validation.md.

---

## 5. docs/background: delete or merge candidates

Nothing here should be deleted without owner approval (AGENTS.md:54). The list gives
the evidence.

Keep (code or docs depend on them):
- `offline-editing-details.md`: rule IDs R1-R13 are cited in code (`frontend/src/lib/data/rebase.ts:2`, `queue-view.svelte.ts:9,13`).
- `svelte-frontend-rewrite.md`: decision numbers are cited in code and tests (`src/pwa_routes.py:11`, `src/admin_access.py:4`, `src/api/admin.py:4`, `src/svelte_frontend.py:56`, `tests/conftest.py:96`). Renaming it means updating these comments.
- `sqlite-wal-timeout.md`: linked from docs/deployment.md:124 and from `src/database_setup.py`.
- `backup-research.md`: the source for plans/backup-options.md.
- `test-suite-speed.md`: linked from README.md:121 and the plan.

Candidates:
- **docs/background/deploy-rehearsal-2026-10-06.md** (70 lines): one-time rehearsal, no incoming links. Delete, or keep as one dated note. Owner call.
- **docs/background/offline-viewing-validation.md** (154 lines): local evidence for Milestone 5, no incoming links. Its conclusions are covered by offline-editing-details.md and svelte-frontend-rewrite.md. Merge the key points into svelte-frontend-rewrite.md, then delete.
- **docs/background/fixes-deployment-2026-10-06.md** (44 lines) and **docs/background/offline-editing-release-validation.md** (35 lines): one-time release records (revision IDs, a jj change ID). Git history holds them. Merge into one "deployments" note, or delete. The second is linked only from offline-editing-details.md.
- **docs/background/nicegui-test-retirement.md** (62) and **docs/background/browser-test-port-map.md** (59): NiceGUI-era test mapping. Only linked from each other and from browser-testing.md:77. Merge into one short history section, or delete with the NiceGUI notes.
- **docs/background/codebase-cleanup.md** (166): all 37 progress items are checked. Move the "Not now" list (around lines 146-156) to backlog Ideas, then delete the file. Update the link at `plans/backlog.md:26`.
- **docs/background/write-atomicity-findings.md** (63): linked only from item-writes background. Merge into docs/background/item-writes.md.
- **docs/background/field-constraints.md** (167): a finished plan. Its rules are now in api.md and the migration. Keep the "reasoning" part, merge with item-writes background.
- **docs/background/offline-findings.md** (54): outcome of a rolled-back experiment. Keep as a short note; it explains why offline was rebuilt.
- **docs/background/android-emulator-testing.md** (23): small. Either fine, or merge into docs/android-emulator-testing.md. Low value.

Many background files repeat the same "NiceGUI app was removed" note (6 files). Keep one note in svelte-frontend-rewrite.md and drop the others when those files are edited.

---

## 6. Gaps for a newcomer

- **G1. No data model.** No doc lists the tables (`rooms`, `lists`, `items`, `room_invitations`,
  `deletions`, `processed_ops`, share-token columns) and what each one is for. ARCHITECTURE.md's
  domain section covers the concepts, not the tables. A short docs/data-model.md would help.
- **G2. No "how to add a feature" guide.** Adding an API op means touching `src/api/ops.py`
  (body model and handler), `frontend/src/lib/data/`, and tests. Nothing says this in order.
  Adding a migration is only in deployment.md:109-113.
- **G3. frontend/README.md has no code map.** Nothing explains that `src/lib/data/` is the
  offline store, `src/lib/room/` is room UI, etc.
- **G4. No plain-language web-basics doc.** AGENTS.md:5 asks for simple explanations of web
  development for learning. There is no glossary (SPA, SSE, cookies, service worker,
  migrations, IndexedDB).
- **G5. No troubleshooting section.** Errors a newcomer will hit are scattered:
  "APP_PASSWORD must be set" (config.py), "Svelte build not found" (deployment.md:63-64),
  "database is locked" (deployment.md:122-124), missing WebKit libraries (browser-testing.md:18-20).
- **G6. Scripts are undocumented.** `scripts/seed_test_data.py` (only its docstring) and
  `scripts/generate_app_icons.py` (nothing).
- **G7. ARCHITECTURE "Code boundaries" is incomplete and ambiguous.** It omits
  `src/api/events.py`, `sign_in_limit.py`, `item_visibility.py`, `field_limits.py`. It says
  `src/api/ops.py` holds "the item and list write rules" (ARCHITECTURE.md:76-77), but
  docs/item-writes.md:21 says the helpers live in `src/database_crud.py`.
- **G8. Environment variables have no single local table.** They are split across README.md:35-37,
  73-77, deployment.md:20-28 and `.env.example`. Acceptable with a link, but a newcomer has to read four places.
- **G9. README does not mention offline use or the SPA.** The intro (README.md:3-8) describes
  shared lists and real-time updates, but not offline editing. Add one line.

---

## 7. Rule conflicts for the owner to decide

- **R1. Length vs. where to put reference material.** The quality rules say top-level docs are
  about one screen and detail goes to `docs/background/`. But background is never the primary
  source for current behavior (AGENTS.md:42). The api.md contract (486 lines) and deployment.md
  have no legal home for their split-out parts. Options: allow reference docs as an exception,
  or add a reference folder that counts as "current behavior".
- **R2. Rollback runbook for NiceGUI.** Is it still needed? If not, item 12 can delete it. If yes,
  it needs to be kept current, and it cannot be (the code is gone).

---

## 8. Proposed cleanup batch

One docs-only change. No deletions, no moved files, no policy edits. AGENTS.md:55 says doc
edits stay within the approved task, so this needs owner approval first.

Contents:
1. docs/api.md: delete the three "1,024 characters" sentences (lines 149, 243, 282). Keep the rule at 87-94. (item 1)
2. docs/home-screen-installation.md:55-59 and docs/deployment.md:133-135: remove localStorage claims. (item 2)
3. docs/public-sharing.md:56: correct the test file name. (item 3)
4. ARCHITECTURE.md:6-7: user count, once the owner picks the number. (item 4)
5. plans/backlog.md: edit wording in place at lines 21, 41, 43, 45. No items removed. (items 5-8)
6. plans/test-suite-speed.md: delete the stale bullet at line 79. (item 9)
7. docs/browser-testing.md: fix the garbled sentence at 74-76. Move the line-20 laptop note to docs/background/browser-testing.md. (items 10, 26)
8. docs/deployment.md:84-86 and 279: reflow only. (item 11)
9. docs/local-network-testing.md:39: rename heading to "Svelte app". (item 25, heading only)
10. docs/room-invitations.md:15: delete the last sentence. (item 24)
11. README.md: add links to docs/offline-viewing.md, docs/change-tracking.md, AGENTS.md (item 16); fix line 113 label (item 15, label only).
12. plans/advanced_sharing.md: add a Progress section. (item 23)

Not in the batch (needs a decision): item 12 (rollback runbook), 13-15 (splits, moves), 18-21 (duplicate removal across many files), 29-30 (staging plan retirement), all background merges (section 5).

Effort: about 45-60 minutes of edits. Verify with the link checker and `grep` for the removed strings. Commit as docs-only in the docs desk, naming only the files changed.

## Orchestrator check
- The "1,024-character password" claim is a FALSE POSITIVE: src/field_limits.py:13 MAX_PASSWORD_LENGTH = 1024 is the request-field limit (sign-in, delete confirm), separate from the 4..72-byte rule for setting passwords. Leave api.md lines 149/243/282 alone (maybe clarify).
- localStorage token claim: no token code in frontend/src/lib/data uses localStorage; likely stale NiceGUI-era text. Verify before editing.
