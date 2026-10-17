# Backlog

Unfinished and deferred work, sorted by commitment. Details live in the linked
plans and docs. How to add and order items is in
[`AGENTS.md`](../AGENTS.md#documentation-lifecycle).

Tags: `bug`, `feature`, `infra`, `data`, `security`, `refactor`, `docs`, `test`.

## Next

In order: the top item is done first.

None.

## Later

Agreed as worth doing; no date.

- [ ] [feature] Offline editing (Milestone 6) (in progress). See [offline editing](offline-editing.md).
- [ ] [feature] Create a list while offline (needs an address before the server gives a slug). See [offline editing](offline-editing.md#what-can-be-done-offline).
- [ ] [feature] Make Admin reachable from inside the app, including the installed room view, without copying or editing a URL. Keep admin password protection. Plan navigation before implementing. See the [offline viewing scope](svelte-frontend-rewrite.md#milestone-5-offline-viewing).

- [ ] [infra] Keep the `/sw.js` kill switch (it removes the old app's service worker from phones) until at least 2027-04-06. Step 5.1 must use a different worker URL (such as `/service-worker.js`) or replace the route carefully; `/sw.js` must never 404 or return the app page. See decision 159 in the [Svelte rewrite plan](svelte-frontend-rewrite.md#decisions-log).
- [ ] [infra] Rehearse a restore on a hosted copy. See [restoration](../docs/deployment.md#restoration-and-rollback).
- [ ] [infra] Add a Railway `staging` environment before production pushes. See the [staging environment plan](staging-environment.md).
- [ ] [security] The sign-in limit per client address trusts the first `X-Forwarded-For` entry, which a client can set. The per-room limit does not depend on it. Check what Railway appends and read the right entry. See [sign-in limit](../docs/api.md#sign-in-limit).
- [ ] [docs] Expand the Allium pilot with a naming-rules spec (trim edges, keep case, Unicode-aware duplicate lists, lowercase items), then judge whether it adds value beyond the tests. See the [Allium pilot](../README.md#allium-pilot-optional) and [UX decisions](../ARCHITECTURE.md#major-ux-decisions).
- [ ] [test] Resume the [test-suite speed plan](test-suite-speed.md#resume-here--remaining-work): decide which Android scenarios and tiers to keep, then benchmark before simplifying.
- [ ] [feature] Longer undo for deleted items and tags: a longer toast time, or an undo history. See decisions 85 and 87 in the [Svelte rewrite plan](svelte-frontend-rewrite.md#decisions-log).
- [ ] [feature] Due dates on items, in stages: first an optional date (no time) shown on the item, then a sort choice for each list: by name (today's default) or by due date. Open items always stay above checked ones. No calendar view. Notifications are in Ideas.
- [ ] [data] Learn and try SQLite WAL mode (readers and a writer at the same time). Small gain today, since one lock serializes database access. See [Not now](../docs/background/codebase-cleanup.md#not-now).

## Ideas

No promise. Revisit when growth, maintenance or product needs justify them. Delete freely.

- [refactor] Evaluate frontend error handling and async workflows: compare [Effect](https://effect.website/) with ordinary TypeScript and, for fetched data/cache management, TanStack Query. Use a small real workflow to compare typed failures, retries, cancellation, debugging and agent maintainability. The Python backend does not block adoption; adopt only if the benefit outweighs added complexity.
- [infra] Evaluate infrastructure as code, including [Alchemy](https://alchemy.run/) and alternatives, against the current Railway deployment workflow. Check Railway support, secrets, persistent SQLite storage, reproducibility, rollback and maintenance cost before proposing any change.
- [infra] Review other tooling that could improve implementation and stability as the Svelte frontend matures. Start with concrete gaps in CI, monitoring/error reporting, dependency updates and deployment checks; compare existing tools with new options rather than adding tools for their own sake. See the CI idea below and the [deployment guide](../docs/deployment.md).
- [security] Raise the four-character password minimum in the future for newly created or changed passwords only. Keep existing passwords valid. Do not redesign login as part of this work. See [password rules](../docs/api.md).
- [infra] Scheduled local backup job that pulls a verified SQLite copy from Railway to this machine or an always-on home machine. Railway snapshots are not available on the current plan. See [backup options](backup-options.md#scheduled-local-copy-railway-snapshots-blocked).
- [infra] Add CI for format, lint and tests. First replace the broad `.*/` ignore rule with explicit runtime-directory rules; keep databases, backups and secrets out of git.
- [feature] Due-date notifications (users asked): remind people when an item is due. Needs web push, a server job and phone permissions (iPhone: home-screen app only). Only after due dates exist.
- [feature] Target realtime refreshes by list/room instead of refreshing all users.
- [feature] Cross-room list pinning, once authorization and UX are designed. See [advanced sharing](advanced_sharing.md).
- [feature] User profiles (individual accounts), only if per-person permissions or revocation are needed. Start the plan with "which problem do we solve?". Possible uses: one login for many rooms, who did what, removing one person without a new room password, controlling who has a share link, admin as a profile, sign-in rate limiting.
- [feature] Bottom toolbar on the list page for thumb reach (for example back, list options, ⋮ menu). The add field stays where it is. Sketch a few layouts and test on the iPhone (Safari's bar, keyboard, home swipe area). After the Svelte switch.
- [refactor] Move `src/` into a proper Python package. (Splitting `src/main.py` is done: since step 4.3 it is only the entry point, and `src/server.py` and `src/api/` hold the rest.)
- [refactor] Replace the global SQLite connection with a connection/context-manager layer.
- [data] Add timestamps and change versions for debugging, conflict detection or audit history.
- [data] Normalize JSON tags into tables if querying or integrity needs it.
- [data] Reconsider the database for multiple replicas, heavy write contention, high availability or multiple regions. Discuss against [`ARCHITECTURE.md`](../ARCHITECTURE.md) first.

## Manual checks

For the owner to do when convenient. Local tests are not production or
real-device evidence. Follow the
[deployment checklist](../docs/deployment.md#deployment-checklist) and record
results (with OS/browser versions for devices) in the linked doc.

- [ ] [test] Gate C: test offline editing on the iPhone, including two devices, before any deploy. Follow the steps in [offline editing](offline-editing.md#steps).
