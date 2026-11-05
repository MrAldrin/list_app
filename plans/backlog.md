# Backlog

Lifecycle: tracked. This is the agenda for unfinished work. Each linked plan
contains the details. An item's position does not give permission to start it.

## How to use this page

- **In progress:** work has started, or waits for review or acceptance.
- **Next:** consider these items next, from top to bottom. Ask before starting.
- **Blocked:** work cannot continue until the stated condition is met.
- **Later:** keep this work, but do not start it next.
- **Ideas:** discuss the proposal before making a plan.
- **Manual checks:** checks that need a person. See the [risk level](../docs/scope.md#risk-level).

Use the same bullet format in every section: **Type — Action**, then a short
explanation and a link where available. Add **Owner decision** when the item
needs the owner's judgment. State dependencies with **Blocked by** and
**Unblocks**, and link both items. A cleared dependency does not approve work.

Ask the owner before adding or moving an item. Put “do this next” at the top
of Next. Keep progress details in the linked plan. When work is complete,
update its documents and remove the item here. Keep any unfinished part as a
separate item. Version control keeps the history.

<span id="current-focus"></span>

## In progress

- **Feature — Finish named item groups.** Work is parked on bookmark `groups`. It is not accepted or ready to deploy. See the [group plan](named-item-groups.md).

Owner questions and recorded answers: [decisions for Heming](decisions-for-heming.md).

## Next

- **Test — Review and improve the test suite.** Review high-risk behavior first. Strengthen useful coverage, fix clear test defects, investigate unreliable tests, and measure runtime against test value. Write a testing guide. Keep coverage removals and broader changes for owner decisions. See the [task plan](test-suite-review.md), including the supporting speed work and remaining Android decisions. Execution approval is pending.
- **Research — Review S3 scope and archived work.** Inspect the saved implementation and recommend the smallest useful in-app reminder feature. Prepare options, reuse/rebuild evidence, and clear decisions for the owner. See the [review assignment](reminders-s3-scope-review.md). Stages 1 and 2, including P2, are accepted on `main`. Research execution approval is pending; S3 implementation stays on hold. **Unblocks:** a later S3 implementation decision, then stages 4 and 5 in Later.

## Blocked

None. Dependencies for work in Next or Later are stated with those items.

## Later

- **Feature — Add stage 4: phone push notifications.** On hold. **Blocked by:** reviewed stage 3 in Next and approval to resume. **Unblocks:** stage 5 below. See the [S4 brief](batches/reminders-s4.md).
- **Feature — Complete stage 5: final polish and owner review.** On hold. **Blocked by:** reviewed stage 4 above, or stage 3 for the in-app-only option, and approval to resume. See the [S5 brief](batches/reminders-s5.md) for the full scope.
- **Feature — Add a custom color-theme picker.** Build on the existing palettes and contrast tests. Start with a ready-made theme. Warn about colors that make text hard to read. See `PALETTES` in `frontend/src/lib/ui/theme.ts`.
- **Feature — Create lists while offline.** A new list needs a usable address before the server assigns its slug. See [offline use](../docs/offline-viewing.md#what-works-offline).
- **Infrastructure — Keep the old service-worker removal route.** Keep `/sw.js` until at least 2027-04-06. The new app must use a different worker URL or replace this route safely. The route must not return a missing-page error or the app page. See [decision 159](../docs/background/svelte-frontend-rewrite.md#decisions-log).
- **Documentation — Extend the Allium pilot.** Specify name trimming, letter case, and duplicate-name rules. Then decide whether the specification adds value beyond tests. See the [pilot](../README.md#allium-pilot-optional) and [UX decisions](../ARCHITECTURE.md#major-ux-decisions).
- **Feature — Give users more time to undo deletion.** Consider a longer toast or an undo history for items and tags. See [decisions 85 and 87](../docs/background/svelte-frontend-rewrite.md#decisions-log).

## Ideas

- **Documentation — Review the remaining October proposals.** **Owner decision.** See the [proposals](improvement-ideas.md) and [recorded decisions](decisions-for-heming.md).
- **Feature — Assess paste rules with a preview.** **Owner decision.** This is a proposal, not approved implementation. See the [paste plan](paste-text-to-list.md).
- **Refactor — Review frontend error handling and asynchronous code.** Compare ordinary TypeScript with [Effect](https://effect.website/). For data fetching and caching, also consider TanStack Query. Compare a small real workflow before adding a tool.
- **Infrastructure — Assess infrastructure as code.** Compare [Alchemy](https://alchemy.run/) and alternatives with the current Railway workflow. Check secrets, SQLite storage, recovery, cost, and maintenance before proposing adoption.
- **Infrastructure — Find concrete gaps in development tools.** Review monitoring, error reporting, dependency updates, and deployment checks. Add tools only when they solve a demonstrated problem. See the [deployment guide](../docs/deployment.md) and the CI proposal below.
- **Security — Increase the minimum password length.** Apply a future increase only to new or changed passwords. Keep existing passwords valid. Do not redesign sign-in. See [password rules](../docs/api.md).
- **Infrastructure — Practise restoring a hosted copy.** See [restoration and rollback](../docs/deployment.md#restoration-and-rollback).
- **Infrastructure — Schedule local production backups.** Pull a verified SQLite copy from Railway to this machine or an always-on home machine. The current plan has no Railway snapshots. See [backup options](backup-options.md#scheduled-local-copy-railway-snapshots-blocked).
- **Infrastructure — Assess continuous integration (CI).** Compare GitHub Actions with local deployment checks. Consider cost, time, maintenance, and safe reuse of checks from the exact revision being deployed. Keep the production backup after checks and immediately before deployment. Before adding CI, replace the broad `.*/` ignore rule with explicit rules that protect databases, backups, and secrets. Railway does not wait for CI unless configured to do so. See the [October review](improvement-ideas.md#tests-and-tooling).
- **Feature — Compress large JSON responses.** Compression reduced a 1,000-item response from 283 KB to 35 KB in an earlier trial. The gain is small for current lists. Never compress Server-Sent Events. See the [performance review](improvement-ideas.md#performance).
- **Feature — Assess sharing between rooms without accounts.** **Owner decision.** No implementation is selected. See the [proposal](cross-room-sharing-without-accounts.md) and [sharing plan](advanced_sharing.md).
- **Feature — Assess optional accounts.** **Owner decision.** Consider accounts if individual permissions or revocation become necessary. See the [proposal](optional-accounts.md).
- **Feature — Choose a visual direction.** **Owner decision.** Review the [mockups and feedback](visual-refresh.md). The owner prefers colorful list cards.
- **Feature — Assess item categories.** **Owner decision.** Categories such as dairy or fruit would divide a list into sections. Tags currently filter items; they do not create sections. See the [owner feedback](visual-refresh.md#owner-feedback-2026-10-19).
- **Refactor — Turn `src/` into a Python package.** The entry point and server code are already separate.
- **Refactor — Replace the global SQLite connection.** Consider a connection manager or context manager.
- **Data — Assess additional timestamps or change history.** Change versions and conflict checks already exist; see [change tracking](../docs/change-tracking.md). Identify a concrete debugging or history need before adding more fields.
- **Data — Store tags in separate tables.** Consider this if queries or data checks require it.
- **Data — Reconsider the database when scaling requires it.** Possible reasons include multiple replicas, frequent competing writes, high availability, or multiple regions. Discuss the [architecture](../ARCHITECTURE.md) first.

## Manual checks

None.
