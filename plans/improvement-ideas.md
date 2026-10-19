# Improvement ideas (October 2026 review)

Lifecycle: tracked

A broad review of ListR on 2026-10-19: code, docs, tests, performance,
security, UX, competitor features and the access model. Eight research agents
gathered the evidence; their full reports are linked at the bottom. This plan
is the menu to choose from. Nothing here is accepted until you pick it.

How to read it:

- **Part 1** lists work already built on review lines (jj workspaces). Each
  line is a chain: keep all of it, the first few changes, or none.
- **Part 2** is the idea catalog by area, with evidence, effort and my view.
- **Part 3** lists the decisions only you can make.

Effort: S = under a day, M = a few days, L = one to two weeks, XL = more.

## Part 1: Built and waiting for review

Each line starts from `integration` and has its own workspace in
`~/projects/<workspace>`. Nothing is integrated or pushed. Review a line with
`jj log -r 'integration..<tip>'` and `jj diff -r <change>`.

Each line passed `pytest`, Ruff, `ty`, `vitest` and the full browser suite
(`-n 4`). The few browser failures did not repeat on rerun and also appear on
the base. All five lines merge with no code conflicts; only
`ARCHITECTURE.md`, `docs/browser-testing.md` and `docs/deployment.md` need a
manual merge when several lines are combined.

| Line (workspace) | Changes, oldest first | Notes for review |
|---|---|---|
| **Backend fixes** (`list_app-ws-backend-fixes`) | `yxosmznt` no-op writes no longer bump the change counter (fixes false "changed meanwhile" conflicts) → `tlulqlqt` bcrypt runs outside the database lock; new all-rooms sign-in limit (30 failures a minute) | A flood of wrong passwords now blocks sign-in for every room for one minute; signed-in devices keep working. Before, it froze the whole app. |
| **Phone UX** (`list_app-ws-phone-ux`) | `xkxonysv` 44 px tap areas → `ykxlvtkz` stable tag colors and distinct letters ("Da", "Dr") → `mknzskoo` checked rows wait 1.5 s, then slide → `uuylrpmn` empty-list hint and a "Clear" chip | Rows grow from 36 to 44 px, so fewer items fit on screen. Two tags can still share a color (7 colors). |
| **Rooms** (`list_app-ws-room-switcher`) | `znrklzkw` Admin in the room menu, shown after an admin sign-in on this device → `ontqompz` "Rooms" list in the room menu to switch rooms | Both new cookies hold no secrets. A room deleted on another device stays in the list until you remove it; decide if you want a remove button. Admin is not in the list ⋮ menu yet. |
| **Ops hardening** (`list_app-ws-ops-hardening`) | `lnttrrtr` frame and sniffing headers → `owprwkyn` `/healthz` → `twnkqukk` deploy script runs all checks before the push (`--browser`, `--skip-checks`) → `zpxvqvlu` GitHub Actions CI → `zvskttol` gzip large JSON responses | Manual steps after deploy: set the Railway healthcheck path to `/healthz`; decide on Railway's "Wait for CI". The first CI run is untested. |
| **Docs cleanup** (`list_app-ws-docs-cleanup`) | `pkzyyxsw` wrong facts and small errors → `svkmropw` one home for each fact; rollback history and the Allium section moved out | Docs only. The user count and the backlog were left for you. |

## Part 2: Idea catalog

### Bugs and correctness

| Idea | Evidence | Effort | View |
|---|---|---|---|
| No-op writes bump the change counter and cause false "changed meanwhile" conflicts | `update_item_done_locked` writes even when unchanged; verified with a stale-page scenario | S | **Built** (backend line) |
| Password checks (bcrypt, ~190 ms) run while holding the one database lock | Measured: one script slows every read from 1.4 ms to ~200 ms; eight to ~1.5 s. Random room names bypass the per-room limit | S-M | **Built** (backend line) |
| 106 "unclosed database" warnings in the tests | `database_setup.py` and `migrations.py` open connections without closing on some paths | S | Do next; cheap hygiene |
| A retried offline quantity change applies twice after 30 days | Processed-op results are pruned after 30 days; documented trade-off | S | Keep as is |

### Security (sized for ~5 users)

| Idea | Evidence | Effort | View |
|---|---|---|---|
| Frame and MIME-sniffing headers | No `X-Frame-Options` or `frame-ancestors` today | S | **Built** (ops line) |
| Full Content Security Policy | SvelteKit inline scripts need hashes or nonces | M | Later; frame headers cover the main risk |
| Admin cookie is signed with the raw `APP_PASSWORD` | A stolen admin cookie allows offline guessing (~0.9 M guesses/s) | S | Worth doing: derive a key with HKDF. Signs admins out once |
| Room tokens never expire on the server | Cookie lasts one year; no "sign out other devices" | S-M | Decide a lifetime (Part 3) |
| Room invitations allow unlimited room creation | Reusable for 7 days, no count | S | Cap at about 5 rooms per invitation |
| Share tokens stored in plain text | Room and invitation tokens are hashed; share tokens must stay readable | M | Accept the risk at this size |
| Docker image runs as root, base images not pinned | `Dockerfile` has no `USER` | S-M | Worth doing, but check Railway volume ownership first. Not built: a mistake can lock the app out of its database |

### Performance

| Idea | Evidence | Effort | View |
|---|---|---|---|
| Gzip large JSON responses | 1,000-item feed: 283 KB raw, 35 KB gzipped | S | **Built** (ops line, last change; Server-Sent Events excluded) |
| Phone rewrites the whole room to IndexedDB on every refresh | Even when nothing changed (`room-store.svelte.ts:397`) | S | Do next, after deciding what "saved at" means |
| Build feed rows after releasing the lock | Worst allowed room holds the lock ~410 ms | S | Only if rooms grow |
| SQLite WAL mode | One connection behind one lock; reads take ~1.5 ms | L | Skip; close the backlog item |
| Normalize JSON tags into tables | No SQL ever reads tags | L | Skip; close the backlog item |
| Target live updates by list | Fan-out cost is negligible at 5 users | M | Skip; close the backlog idea |

### Code cleanup

| Idea | Evidence | Effort | View |
|---|---|---|---|
| Typing gaps: `db: Any` hides 78 database calls from `ty` | `database_setup.py:652`; `lastrowid` returned as `int` from `int \| None` | S | Do next; enables the split below |
| Split `database_crud.py` (1,098 lines, eight concerns) | `room_invitations.py` reaches into the private lock | M | After typing |
| One room-creation path | Three paths with different slug formats and duplicate checks | S | Do with the split |
| Dead and test-only code | `get_lists`, `wake_streams(None)`, listener seam | S | Do with the split |
| Frontend error model | Same code twice with different fallback texts; `code` is a plain string | S-M | Do next; makes the refactors below safer |
| Split the 900-line `RoomHandle` and the 830-line `RoomStore` | `data/index.ts`, `room-store.svelte.ts` | M-L | After the error model |
| Move the visible-items pipeline out of `ListView.svelte` | Three copies of the undo-toast code | S-M | Good first frontend refactor |
| Effect or TanStack Query | The hard parts are the offline queue and conflict rules, which neither replaces | — | No; close the backlog idea |
| Move `src/` into a Python package | 82 files import flat modules | M | Skip for now |

### Tests and tooling

| Idea | Evidence | Effort | View |
|---|---|---|---|
| Run the checks in the deploy script before pushing | It pushes `main` with no test run today | S | **Built** (ops line) |
| GitHub Actions CI | None today; `.gitignore` hides `.github/` | S-M | **Built** (ops line). Railway still deploys unless "Wait for CI" is on |
| `/healthz` and a Railway healthcheck | No health route | S | **Built** (ops line) |
| Dependency update bot | A merged bot PR to `main` deploys without a backup | S | Only if it targets `integration` |
| Flaky frontend test and duplicated test fakes | `offline-integration.test.ts:1505` uses a 1 s wait | S | Do next |
| Faster sign-in limit tests | ~16 s CPU from real bcrypt | S | Small win |
| Trim overlapping browser tests | ~27 offline tests in 5 files; ~20 old-URL tests retire with the `/sw.js` kill switch | M | Part of the [test-suite speed plan](test-suite-speed.md) |
| Replace 14 fixed waits in browser tests | A fixed wait can let a negative check pass falsely | S-M | Do next |

### Docs

| Idea | Evidence | Effort | View |
|---|---|---|---|
| Fix wrong facts and broken references | localStorage claims, a wrong test file name, a garbled sentence | S | **Built** (docs line) |
| One home per fact; shorter top-level docs | The manual-check rule is copied into 7 files; `deployment.md` is 283 lines | S-M | **Built** (docs line) |
| User count: "four" or "five" | `ARCHITECTURE.md` vs `AGENTS.md` | S | You pick (Part 3) |
| Retire the staging plan | Its `staging` bookmark conflicts with the bookmark rules | S | Needs your approval |
| Move the finished cleanup's "Not now" list to the backlog | `docs/background/codebase-cleanup.md` is 37/37 done | S | Needs your approval |
| Split `docs/api.md` (486 lines) | Over the one-screen rule | M | Later; split by area (rooms, items, admin) |

### UX and design

The colors pass WCAG AA in both themes. The real problems are tap sizes,
moving rows and tag clarity. Screenshots are in the [UX report](#reports).

| Idea | Evidence | Effort | View |
|---|---|---|---|
| 44 px tap areas | Quantity buttons 20×28, tag letters 26×26, toast Undo 32 px | S | **Built** (phone line) |
| Stable tag colors, distinct letters | "Dairy" and "Dry goods" both show "D"; colors follow tag position | S | **Built** (phone line) |
| Checked rows stay in place briefly | The next row slides under your thumb | S | **Built** (phone line) |
| Empty-list hint and "Clear" for the tag filter | No message on an empty list; one tap per chip to clear | S | **Built** (phone line) |
| Enter adds half-typed search text | Typing "mil" + Enter adds "mil"; search only filters offline | S-M | You decide (Part 3) |
| No toast on every check; one undo bar | Three toasts can cover ~110 px | S | You decide (Part 3) |
| Keep item names in your capitals | "iPhone charger" shows as "iphone charger" | M | You decide (Part 3) |
| Split Options into "Edit" and "Settings" | Opening settings also shows a trash can on every row | M | Good idea |
| Sort button next to the title | Sort takes 4 taps today | S | Good idea |
| One-line offline banner | Takes ~160 px today | S | Good idea |
| Connection pill overlaps Options | By CSS geometry | S | Fix with the banner |
| Item editor as a bottom sheet | Save sits mid-screen | M | With the bottom bar |
| **Bold:** bottom toolbar (add field, Options, Sort, menu) | All controls are at the top today | L | Biggest UX gain; already in the backlog |
| **Bold:** swipe to check or delete; group by tag | — | M | Try after the bottom bar |
| Type scale and spacing tokens | ~12 font sizes, ad-hoc spacing | S | Cleanup, low priority |

### Features

From the [feature research](#reports) (13 apps compared) and the code review.

| Idea | Who has it | Effort | View |
|---|---|---|---|
| **Usual items:** suggest what you add often | Listonic, OurGroceries, AnyList | S-M | Top pick; the "times added" data exists |
| **"I'm shopping" status:** others see it live | (rare) | S-M | Top pick for a family; uses the live stream |
| **Store aisle order:** tags become aisles, drag them into store order | Bring!, AnyList, Mealie, Reminders | M | Top pick; extends sorting |
| **Paste text to list:** split a message or recipe into items, confirm | Several iOS apps | S | Rules first; AI later if needed |
| **Recurring items / list templates** | Shopper, Grocy | M | May beat recipe import for this group |
| Recipe URL import | AnyList, Bring!, Paprika, Mealie | L | Messy sites; do after paste-to-list |
| Activity history: who added or checked what | Shopper | M | Needs a name per device or accounts |
| Item notes and units | AnyList, Bring! | S | Notes exist; units are small |
| Longer undo / undo history | — | S | Already in the backlog |
| Due-date reminders | — | M-L | Already in the backlog |
| Share target ("Share to ListR" from other apps) | — | S-M | Android only; iOS unverified |
| Push notifications | Listonic | M | iPhone only for installed apps (iOS 16.4+) |
| Telegram bot | Open-source bots | M | Fun; needs a secret link code per room |
| Photos on items | Bring!, Listonic | M | Low value |
| Price tracking, barcode scanning | Listonic, Grocy | M | Skip for a family list |
| **Crazy:** meal plan → combined list | AnyList, Mealie | L | After recipe import |
| **Crazy:** AI "what are we missing?" from history | — | M | Fun; needs an API key and a cost limit |
| **Crazy:** native wrapper (Capacitor) for widgets and store geofences | Bring!, AnyList | XL | A stack change; only if widgets matter |

### Accounts, rooms and admin

The question you raised: your own room, a shared room with your partner, lists
in both, and extra features for people with an account. The full design is in
the [accounts report](#reports).

What is clunky today:

- No way to reach Admin from the installed app; only `/` has the button.
- Admin cannot enter a room without its password, so the only shortcut is a
  reset, which signs everyone out of that room.
- The browser remembers only one room.
- Removing one person means a new password for everyone.

Options, smallest first. Each step ships on its own:

1. **A: Admin entry plus a room switcher** (S + S, no database change).
   **Built** (rooms line). Covers "my room and our room" today.
2. **B1: Show one list in two rooms** (M-L, one new table). Works without
   accounts: a browser that holds both rooms' access can link a list. The hard
   part is change tracking per room, not login. Decide what the second room
   may do (Part 3).
3. **C: Optional accounts on top of rooms** (L). Username and password first,
   passkeys later. Rooms keep working with their passwords. Accounts unlock a
   personal room, "my rooms" from memberships, who-did-what, removing one
   person and, later, notifications. New tables: `users`, `user_sessions`,
   `room_members`.
4. **D: Accounts replace room passwords** (XL). Not recommended: it breaks
   the zero-setup sharing that works today.

Admin ideas: admin as a role on an account (after C); show list count and last
activity in the admin room list; derive the admin cookie key properly (see
Security).

My recommendation: ship A now, use it for a few weeks, then decide between
B1 and C. If "who did what" or removing one person matters, go to C and build
B on top of it.

## Part 3: Decisions for you

1. Which review lines to keep, partly or fully (Part 1).
2. Add field: should Enter pick the matching suggestion instead of adding
   half-typed text? This changes an `ARCHITECTURE.md` UX decision.
3. Toasts: drop the toast on every check and keep one undo bar?
4. Item names: keep your capitals, and match duplicates without case?
   Needs a data step and an `ARCHITECTURE.md` change.
5. Room tokens: give them a lifetime (for example 180 days)?
6. User count in the docs: four or five?
7. Sharing across rooms: B1 now, or wait for accounts (C)?
8. Close the backlog items for WAL, tag tables, targeted live updates and
   Effect/TanStack Query, based on the evidence above?
9. Your top three features from the list above.

## Reports

The full agent reports (evidence, file and line references, measurements) are
in [`docs/background/improvement-review-2026-10/`](../docs/background/improvement-review-2026-10/):

- [Backend](../docs/background/improvement-review-2026-10/backend.md),
  [frontend](../docs/background/improvement-review-2026-10/frontend.md),
  [performance and security](../docs/background/improvement-review-2026-10/perf-security.md)
- [Docs audit](../docs/background/improvement-review-2026-10/docs.md),
  [tests and tooling](../docs/background/improvement-review-2026-10/tooling.md)
- [UX review](../docs/background/improvement-review-2026-10/ux.md),
  [feature research](../docs/background/improvement-review-2026-10/features.md),
  [accounts, rooms and admin](../docs/background/improvement-review-2026-10/accounts.md)

Some reports are condensed copies, and line numbers date from 2026-10-19.
The UX screenshots stayed outside the repo. Delete reports that stop being
useful once their ideas are decided.

## Progress

- [x] Research: eight areas reviewed
- [x] Review lines built and verified (Part 1)
- [ ] Owner decisions (Part 3)
- [ ] Accepted ideas moved to the backlog; plan retired
