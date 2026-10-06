# Staged frontend migration for offline use

Lifecycle: tracked

## Status and scope

This file holds the direction and the reasons. The step-by-step work, milestones
and owner gates are in the [Svelte rewrite plan](svelte-frontend-rewrite.md).
See [experiment findings](../docs/background/offline-findings.md) for the rollback report,
evidence and limitations. The shipped architecture is the Svelte frontend with a Python JSON API (the NiceGUI app was removed in Milestone 4).

## Target

Use a browser-side frontend that can run without the Python server. Keep Python
for server-side business rules, authorization and API endpoints; retain SQLite
and Railway unless a separate requirement justifies changing them. Native iPhone
packaging is not a prerequisite.

## Frontend decision

Owner decision (2026-09-29): **Svelte 5 with SvelteKit in static/SPA mode**
(`adapter-static`), written in TypeScript. The built frontend is static files
that talk to the Python API.

- Chosen for readable, compact code, a small app with few users, and SvelteKit's
  built-in service worker support.
- Considered: React (largest ecosystem, React Native path, best AI coverage) and
  Vue. Neither advantage applies to current goals. Rust/WebAssembly frameworks
  were rejected as a third language with little benefit.
- NiceGUI 3.17 has no offline support or roadmap for it; the community
  `nicegui-pyodide` project is experimental and does not support `@ui.page`.
- Pin Svelte 5 syntax (runes such as `$state`) in project guidance so generated
  code does not mix in Svelte 4 patterns.

## Where the work lives

- The online app is deployed. For offline continuation, follow the current
  [branch instructions](svelte-frontend-rewrite.md#branches), not the earlier
  `svelte-frontend` starting point. Bookmark moves and rebases need approval.
- Put the Svelte project in `frontend/`; Python stays in `src/`.
- Offline work stays off production until separately approved. Pushing `main`
  deploys; follow the deployment checklist. Do not build on the historical
  offline experiment or the owner's learning line.

## Learning approach

The owner learns Svelte by hand on the `svelte-learning` branch, separate from
the implementation. That branch is practice code and is never merged.

## Order of work

Owner decision (2026-10-03): build an online prototype first, test it on the
laptop and the iPhone, then migrate the rest, then add offline viewing and
editing. Offline is built last but designed for from the start (see below), so
no part needs a second rewrite. Milestones and gates are in the
[Svelte rewrite plan](svelte-frontend-rewrite.md).

- Keep server-side access checks and business rules in Python; do not duplicate
  them in the new UI.
- Offline viewing can ship before offline editing.
- Do not rely on iPhone background synchronization while the app is closed.

## Design early to avoid a second rewrite

Before settling the API and local storage model, specify:

- Stable, non-reused identities, including a way to create IDs offline later.
- Server change versions and deletion representation, so stale devices cannot
  accidentally restore deleted records or overwrite newer changes unnoticed.
- A local data layer designed for updates, schema upgrades and later pending
  operations, rather than a display-only snapshot format.
- Retry-safe write requests and explicit conflict rules for edits/deletions,
  duplicate names and multiple devices. Do not assume timestamps alone solve this.
- Privacy and authorization rules for saved data: logout, revoked room access,
  shared devices and storage loss. Revocation cannot instantly erase an offline
  device's saved copy; reconnection must revalidate before accepting writes.
- Device tests covering cold launch, reconnect, storage loss, deployment updates
  and multi-device changes. Browser storage is not a guaranteed permanent backup.

These are design obligations, not implemented capabilities. Full sync mechanics
can follow later, but the read-only design must leave room for them.

## Keeping the direction consistent across Jujutsu stacks

- Put this decision in a documentation-only change directly above `main`; the
  owner manages integration and the `main` bookmark.
- Documentation is versioned with each revision, not shared automatically across
  branches. After review, rebase active stacks onto this documentation baseline
  (or onto main after the owner integrates it).
- Inspect each stack's base and documentation conflicts individually. Reconcile
  historical claims of implemented offline support with the current disposition;
  do not blindly keep one side of a conflict or bulk-rebase unrelated work.
- Leave the old offline experiment unchanged as historical evidence. It need not
  receive current documentation if it is no longer an active development stack.
- Do not cherry-pick independent copies of the same documentation change into
  every stack; prefer common ancestry to reduce future divergence.

## Progress

- [x] Record the owner-reported rollback, evidence limits and future direction.
- [x] Document staged viewing-to-editing migration and early design obligations.
- [ ] Owner reviews/integrates the shared documentation baseline.
- [ ] Rebase selected active stacks after explicit approval; preserve experiment.
- [x] Choose frontend: Svelte 5 + SvelteKit static/SPA (2026-09-29).
- [x] Guided Svelte basics walkthrough (continues on `svelte-learning`).
- [x] Agree milestones and gates: see the [Svelte rewrite plan](svelte-frontend-rewrite.md) (2026-10-03).
- [ ] Implementation, testing and gates: tracked in the rewrite plan.
