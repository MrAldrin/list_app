# Backlog

Lifecycle: tracked. The one agenda of unfinished work. Placement is neither
permission nor strict order. Details live in the linked plans and docs.

## How to maintain this backlog

- **Current focus:** selected work. **Next:** ready, in order, top first.
  **Blocked:** waiting on a named prerequisite. **Later:** agreed, deferred.
  **Ideas:** needs shaping or a decision; delete freely. **Manual checks:** rare,
  see the [risk level](../docs/scope.md#risk-level).
- Each item starts with a tag, then a short description and a link. Tags:
  `bug`, `feature`, `infra`, `data`, `security`, `refactor`, `docs`, `test`.
  Add `[human]` when the item needs substantial owner judgment.
- "Do this next" goes at the top of Next. For any other new item, ask which
  section it goes in, and where in Next if chosen. Move items between sections
  only when the owner decides.
- Mark work that spans sessions `(in progress)`.
- Link real dependencies both ways with **Blocked by** and **Unblocks**.
  Unblocking does not select an item.
- When work finishes, update the owning docs and any dependents, then remove the
  item. Record leftover work as its own item. Version control keeps history.

## Current focus

- [ ] [feature] Implement [named item groups](named-item-groups.md). (in progress) Parked on bookmark `groups` (rebuilt on `integration`, not accepted). Not shipping yet.

Owner answers and any further questions: [decisions for Heming](decisions-for-heming.md).

## Next

Cloud delivery order (owner, 2026-11-02). Each task is one Claude Code cloud
session that follows [`CLAUDE.md`](../CLAUDE.md) and opens a pull request into
`integration`. Merging needs the owner's approval; browser tests are rerun
locally before merging.

- **Wave 1, in parallel:** tag "+" chip, Sort, themes step 1, in-app reminders.
- **Wave 2, one session in order, after wave 1 is merged:** bottom bar,
  scrollable suggestions, usual items. All three rebuild the add area.

- [ ] [feature] Remove the "+" add-tag chip from the tag row (`frontend/src/lib/list/ListTags.svelte`). New tags are added in **Options → Tags**, as today.
- [ ] [feature] Split the Sort menu into two controls: what to sort by (name, date, added, most added) and the direction (high to low or low to high), instead of eight fixed choices. The data already stores a key and a direction (`ITEM_SORTS` in `frontend/src/lib/data/order.ts`); keep saved choices working. See [sorting items](../docs/item-sorting.md).
- [ ] [feature] Color themes, step 1: about five ready-made themes (each with light and dark), chosen in the menu and saved in the browser like dark mode. Base them on well-known open palettes (for example Catppuccin, Nord, Solarized, Gruvbox or Dracula; check each license). Colors already live in CSS variables (`frontend/src/app.css`, `frontend/src/lib/ui/theme.svelte.ts`). Every theme keeps text at 4.5:1 contrast. Build the theme list so step 2 can add a custom one.
- [ ] [feature] Due-date reminders inside the app (options 1 and 2 of the [sketch](due-date-reminders.md)): a toast when a list opens, and a check across all lists while the app is open, re-run every few minutes. "Soon" means due today or tomorrow, and overdue items count too. Frontend only. Phone push (option 3) stays in Later.
- [ ] [feature] Bottom bar for the thumb on phones: move add/search to the bottom of the list page. The implementing agent decides whether Options, Sort and the menu also move down, and may move more if it judges that better; record the choice in the docs. Toasts move to the top. See [visual refresh](visual-refresh.md#open-questions).
- [ ] [feature] Scrollable typing suggestions: while typing in **Add or Search**, show more than the top three matches in a list that scrolls, best matches first (today capped by `MAX_SUGGESTIONS` in `frontend/src/lib/list/items.ts`). Keep the keyboard rules in [adding items](../docs/adding-items.md); fit with the bottom bar item above.
- [ ] [feature] Redesign usual items so they no longer take space under the add field. Move them to their own place, opened on demand: for example a button in the add area, or a "Most added" button that opens a pop-up or sheet. The implementing agent picks the most intuitive design, builds it and explains the choice; the owner reviews the result. Keep the current ranking and offline behavior unless the design needs a change. See [adding items](../docs/adding-items.md).

## Blocked

## Later

- [ ] [feature] Color themes, step 2: a custom theme picker built on step 1. Start from a ready-made theme and change a few colors (background, accent, text); warn or adjust when text would be hard to read.
- [ ] [feature] Phone push reminders when the app is closed (option 3 of the [due-date sketch](due-date-reminders.md)). Needs a push service, a scheduled job and an architecture change.
- [ ] [feature] Create a list while offline (needs an address before the server gives a slug). See [offline use](../docs/offline-viewing.md#what-works-offline).
- [ ] [infra] Keep the `/sw.js` kill switch (it removes the old app's service worker from phones) until at least 2027-04-06. Step 5.1 must use a different worker URL (such as `/service-worker.js`) or replace the route carefully; `/sw.js` must never 404 or return the app page. See decision 159 in the [Svelte rewrite record](../docs/background/svelte-frontend-rewrite.md#decisions-log).
- [ ] [docs] Expand the Allium pilot with a naming-rules spec (trim edges, keep case, Unicode-aware duplicate lists, lowercase items), then judge whether it adds value beyond the tests. See the [Allium pilot](../README.md#allium-pilot-optional) and [UX decisions](../ARCHITECTURE.md#major-ux-decisions).
- [ ] [test] Resume the [test-suite speed plan](test-suite-speed.md#resume-here--remaining-work): decide which Android scenarios and tiers to keep, then benchmark before simplifying.
- [ ] [feature] Longer undo for deleted items and tags: a longer toast time, or an undo history. See decisions 85 and 87 in the [Svelte rewrite record](../docs/background/svelte-frontend-rewrite.md#decisions-log).
- [ ] [refactor] Switch the live-update stream to FastAPI's built-in Server-Sent Events (`EventSourceResponse`, FastAPI 0.135+) to drop our keep-alive code. Do it next time `src/api/events.py` changes. See [Not now](../docs/background/codebase-cleanup.md#not-now).
- [ ] [data] Learn and try SQLite WAL mode (readers and a writer at the same time). Small gain today, since one lock serializes database access. See [Not now](../docs/background/codebase-cleanup.md#not-now).
- [ ] [test] Stable room codes in the local preview: `serve_svelte_local.py --seed` (via `scripts/seed_test_data.py`) should give Home and Cabin the same room codes every time, so a browser that remembers a room from an earlier preview can still sign in. Today each new preview database makes new random codes, and the old remembered room fails with "wrong room or password".

## Ideas

- [docs] [human] Review remaining proposals in the [October improvement ideas](improvement-ideas.md); the owner's recorded choices are in [decisions for Heming](decisions-for-heming.md).
- [feature] [human] Assess [rule-based paste with preview](paste-text-to-list.md); plan only, not approved for implementation.
- [refactor] Evaluate frontend error handling and async workflows: compare [Effect](https://effect.website/) with ordinary TypeScript and, for fetched data/cache management, TanStack Query. Use a small real workflow to compare typed failures, retries, cancellation, debugging and agent maintainability. The Python backend does not block adoption; adopt only if the benefit outweighs added complexity.
- [infra] Evaluate infrastructure as code, including [Alchemy](https://alchemy.run/) and alternatives, against the current Railway deployment workflow. Check Railway support, secrets, persistent SQLite storage, reproducibility, rollback and maintenance cost before proposing any change.
- [infra] Review other tooling that could improve implementation and stability as the Svelte frontend matures. Start with concrete gaps in CI, monitoring/error reporting, dependency updates and deployment checks; compare existing tools with new options rather than adding tools for their own sake. See the CI idea below and the [deployment guide](../docs/deployment.md).
- [security] Raise the four-character password minimum in the future for newly created or changed passwords only. Keep existing passwords valid. Do not redesign login as part of this work. See [password rules](../docs/api.md).
- [infra] Rehearse a restore on a hosted copy. See [restoration](../docs/deployment.md#restoration-and-rollback).
- [infra] Scheduled local backup job that pulls a verified SQLite copy from Railway to this machine or an always-on home machine. Railway snapshots are not available on the current plan. See [backup options](backup-options.md#scheduled-local-copy-railway-snapshots-blocked).
- [infra] Add CI for format, lint and tests. First replace the broad `.*/` ignore rule with explicit runtime-directory rules; keep databases, backups and secrets out of git. A ready GitHub Actions workflow (Python, frontend and browser jobs, pinned actions) was built and dropped in the [October review](improvement-ideas.md#tests-and-tooling); the deploy script now runs the same checks locally. Railway deploys regardless unless "Wait for CI" is on.
- [feature] Gzip large JSON responses (a 1,000-item feed drops from 283 KB to 35 KB). Server-Sent Events must stay uncompressed. Built and dropped in the [October review](improvement-ideas.md#performance); low gain at today's list sizes.
- [feature] Target realtime refreshes by list/room instead of refreshing all users.
- [feature] [human] Assess [cross-room sharing without accounts](cross-room-sharing-without-accounts.md); no implementation selected. See also [advanced sharing](advanced_sharing.md).
- [feature] [human] Assess [optional accounts](optional-accounts.md) if individual permissions or revocation are needed; no implementation selected.
- [feature] [human] Visual refresh: pick a direction from the [mockups and feedback](visual-refresh.md). The owner likes colorful list cards. The bottom bar and themes are in Next.
- [feature] [human] Item categories (dairy, dry goods, fruit and veg) that group a list into sections, as in the Aisles mockup. Tags only filter today, so this needs its own design. See [visual refresh](visual-refresh.md#owner-feedback-2026-10-19).
- [refactor] Move `src/` into a proper Python package. (Splitting `src/main.py` is done: since step 4.3 it is only the entry point, and `src/server.py` and `src/api/` hold the rest.)
- [refactor] Replace the global SQLite connection with a connection/context-manager layer.
- [data] Add timestamps and change versions for debugging, conflict detection or audit history.
- [data] Normalize JSON tags into tables if querying or integrity needs it.
- [data] Reconsider the database for multiple replicas, heavy write contention, high availability or multiple regions. Discuss against [`ARCHITECTURE.md`](../ARCHITECTURE.md) first.

## Manual checks

None.
