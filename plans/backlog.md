# Backlog

Unfinished and deferred work, sorted by commitment. Details live in the linked
plans and docs. How to add and order items is in
[`AGENTS.md`](../AGENTS.md#documentation-lifecycle).

Tags: `bug`, `feature`, `infra`, `data`, `security`, `refactor`, `docs`, `test`.

## Next

In order: the top item is done first.

- [ ] [feature] (in progress) Svelte frontend rewrite, on the `svelte-frontend` branch only: prototype, migration, then offline. Follow the [Svelte rewrite plan](svelte-frontend-rewrite.md).

## Later

Agreed as worth doing; no date.

- [ ] [infra] Keep the `/sw.js` kill switch (it removes the old app's service worker from phones) until at least 2027-04-06. Step 5.1 must use a different worker URL (such as `/service-worker.js`) or replace the route carefully; `/sw.js` must never 404 or return the app page. See decision 159 in the [Svelte rewrite plan](svelte-frontend-rewrite.md#decisions-log).
- [ ] [infra] Rehearse a restore on a hosted copy. See [restoration](../docs/deployment.md#restoration-and-rollback).
- [ ] [infra] Add a Railway `staging` environment before production pushes. See the [staging environment plan](staging-environment.md).
- [ ] [data] Strengthen field constraints: nullable names, completion state and slugs; quantities below one; length limits; valid tags JSON. Inspect existing data first.
- [ ] [data] Hide-done numbers: require at least 1 for "After X days" and "Keep last X" (0 acts like "All"). Change the Svelte field, the API check and saved zeros together. See the [Svelte rewrite plan](svelte-frontend-rewrite.md#gate-a-checklist).
- [ ] [security] Old room passwords may still sit in some browsers' localStorage (the NiceGUI app deleted them on each visit since 2026-09-18, then was removed in step 4.3, together with the dated cleanup code). The Svelte app does not clean them. Decide whether the Svelte start page should delete those old keys once, or drop this item. The key names are in the old `src/main.py` (`_cleanup_legacy_room_password_keys`), visible in jj history.
- [ ] [docs] Expand the Allium pilot with a naming-rules spec (trim edges, keep case, Unicode-aware duplicate lists, lowercase items), then judge whether it adds value beyond the tests. See the [Allium pilot](../README.md#allium-pilot-optional) and [UX decisions](../ARCHITECTURE.md#major-ux-decisions).
- [ ] [test] Resume the [test-suite speed plan](test-suite-speed.md#resume-here--remaining-work): decide which Android scenarios and tiers to keep, then benchmark before simplifying.
- [ ] [security] Room sign-in answers faster for an unknown room than for a wrong password, because bcrypt is skipped. This reveals which rooms exist. Check a dummy hash for unknown rooms. See `authenticate_room_and_issue_token` in [`src/database_crud.py`](../src/database_crud.py).
- [ ] [bug] The item tag filter keeps filtering by a tag after it is deleted elsewhere, while the tag button is gone. This was the NiceGUI behavior. The Svelte list page already clears the filter in `activeFilter` ([`tags.ts`](../frontend/src/lib/list/tags.ts)); verify it in a browser test, then remove this item.
- [ ] [feature] Longer undo for deleted items and tags: a longer toast time, or an undo history. See decisions 85 and 87 in the [Svelte rewrite plan](svelte-frontend-rewrite.md#decisions-log).
- [ ] [feature] Admin can delete a room from the admin room list, without entering the room: a clear warning, type the room name to confirm, and tests that nothing else is deleted. Today the admin must reset the password, enter the room and delete it there (as in NiceGUI).

## Ideas

No promise. Revisit when growth, maintenance or product needs justify them. Delete freely.

- [refactor] Evaluate frontend error handling and async workflows: compare [Effect](https://effect.website/) with ordinary TypeScript and, for fetched data/cache management, TanStack Query. Use a small real workflow to compare typed failures, retries, cancellation, debugging and agent maintainability. The Python backend does not block adoption; adopt only if the benefit outweighs added complexity.
- [infra] Evaluate infrastructure as code, including [Alchemy](https://alchemy.run/) and alternatives, against the current Railway deployment workflow. Check Railway support, secrets, persistent SQLite storage, reproducibility, rollback and maintenance cost before proposing any change.
- [infra] Review other tooling that could improve implementation and stability as the Svelte frontend matures. Start with concrete gaps in CI, monitoring/error reporting, dependency updates and deployment checks; compare existing tools with new options rather than adding tools for their own sake. See the CI idea below and the [deployment guide](../docs/deployment.md).
- [security] Enforce a minimum password length in code.
- [infra] Scheduled local backup job that pulls a verified SQLite copy from Railway to this machine or an always-on home machine. Railway snapshots are not available on the current plan. See [backup options](backup-options.md#scheduled-local-copy-railway-snapshots-blocked).
- [infra] Add CI for format, lint and tests. First replace the broad `.*/` ignore rule with explicit runtime-directory rules; keep databases, backups and secrets out of git.
- [feature] Target realtime refreshes by list/room instead of refreshing all users.
- [feature] Cross-room list pinning, once authorization and UX are designed. See [advanced sharing](advanced_sharing.md).
- [feature] User profiles (individual accounts), only if per-person permissions or revocation are needed. Start the plan with "which problem do we solve?". Possible uses: one login for many rooms, who did what, removing one person without a new room password, controlling who has a share link, admin as a profile, sign-in rate limiting.
- [feature] Svelte list page: a "5 checked items hidden" line at the bottom when hide-done hides items. See decision 89 in the [Svelte rewrite plan](svelte-frontend-rewrite.md#decisions-log).
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

- [ ] Finish the deployment guide's outstanding production checks: persistence across restart/deployment, migration verification, remembered room access and password-reset revocation.
- [ ] Confirm production startup logs show no duplicate-name migration error after deploying the unique item-name index.
- [ ] Verify the [checked-item visibility](../docs/checked-item-visibility.md#existing-lists-and-verification) migration on production and real devices.
- [ ] Before the Svelte switch (Gate B): check the Railway service uses the new `Dockerfile` build, has no dashboard build or start command, and still has the volume at `/data` and `DB_PATH`. See [production image](../docs/deployment.md#production-image).
- [ ] After the Svelte switch on production: sign in to a room over HTTPS and check in the browser's cookie view that `__Host-listapp-room-...` exists (Secure). If the cookie has no `__Host-` prefix, set Railway `FORWARDED_ALLOW_IPS=*`. Also check a room you were signed in to before the switch still opens without a password. See the [rehearsal note](../docs/background/deploy-rehearsal-2026-10-06.md#https-detection-and-forwarded-headers).
- [ ] Confirm on Railway that automatic reload is off by default. See [deployment configuration](../docs/deployment.md#configuration).
- [ ] Do the [public-sharing deployment and device checks](../docs/public-sharing.md#rollout-and-verification).
- [ ] Verify deleted-list handling with multiple users on real devices or production. Local coverage is in [browser testing](../docs/browser-testing.md#deleted-list-regression-checks).
- [ ] Run the [deploy backup script](../docs/deployment.md#backup-before-deploying) with `--backup-only` once. Check that a verified copy lands locally and no `list-deploy-*` file is left on the volume.
- [ ] Run the real iPhone and Android checklist in [home-screen installation](../docs/home-screen-installation.md).
- [ ] [test] Svelte home-screen install on the iPhone (Safari, HTTPS): sign in to a room at `/room/…`, then Add to Home Screen. The icon should open that room without a second sign-in. Also install from the start page (opens `/`), and with a NiceGUI icon already installed (note whether the browser reuses it). See the [Svelte rules](../docs/home-screen-installation.md#svelte-app).
- [ ] [test] Svelte on the iPhone: go offline, then back online, and wait up to 30 s without refreshing. If the pill stays longer, file a reconnect bug. One case on 2026-10-04 hung ~10 s (within the retry delays). See decisions 67 and 92 in the [Svelte rewrite plan](svelte-frontend-rewrite.md#decisions-log).
- [ ] [test] Svelte dark mode on the iPhone: with a page open, switch the iPhone's dark mode, then use the moon button. Safari's bars should change color at once, without scrolling. The `theme-color` tag follows the page (decision 138 in the [Svelte rewrite plan](svelte-frontend-rewrite.md#decisions-log)).
