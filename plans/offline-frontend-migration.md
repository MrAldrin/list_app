# Staged frontend migration for offline use

Lifecycle: tracked

## Status and scope

Direction agreed with the owner; implementation is deferred and requires explicit
approval. Continue small improvements to the current app in the meantime.
See [experiment findings](../docs/background/offline-findings.md) for the rollback report,
evidence and limitations. The current shipped architecture remains NiceGUI.

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

- Develop on the `svelte-frontend` bookmark, branched from `main`. Rebase it
  onto `main` regularly to keep conflicts small. Do not build on
  `backup-offline-read-only`; it is reference only.
- Put the Svelte project in `frontend/`; Python stays in `src/`.
- Additive Python API endpoints may land on `main` in small, separately approved
  slices before the switch, so the final switch mainly changes which frontend is
  served. Pushing `main` deploys; follow the deployment checklist.

## Learning approach

The owner is new to Svelte and JavaScript; so far the app has been pure Python.
Treat the first sessions as guided learning, not fast delivery.

- Move slowly at the start: one small concept per step. Explain what a step does
  and why before writing code, then recap and wait for the owner before moving on.
- Compare with Python where it helps: npm ≈ uv, `package.json` ≈ `pyproject.toml`,
  `package-lock.json` ≈ `uv.lock`, `node_modules/` ≈ `.venv/`.
- Let the owner type or run key commands when it aids learning; review afterwards.
- Cover the basics roughly in this order before the prototype:
  1. What runs in the browser vs. on the server, and what "static files" means.
  2. A `.svelte` component: `<script>`, markup and `<style>` in one file.
  3. Svelte 5 runes: `$state`, `$derived`, `$props`, then `$effect` sparingly.
  4. Template logic and events: `{#if}`, `{#each}`, `onclick`.
  5. SvelteKit routing (`src/routes/+page.svelte`) and fetching from the Python API.
  6. Building to static files and how Python serves them.
- Tooling: Node 24 (via `fnm`) and npm are already installed; no global installs.
  Create the project with `npx sv create frontend` once approved. Use npm, the
  default in the Svelte docs, rather than bun.

## Small, testable stages

1. **Validate a thin prototype before committing to a full migration.** One list
   on the actual iPhone: open online, save locally, close, enable airplane mode,
   and reopen from the home screen. Verify saved content and clear stale/offline
   indicators. Prototype the eventual synchronization contract, including a
   two-device conflict, before treating the design as settled.
2. **Introduce the new frontend online first.** Agree the API and authorization
   boundary, then migrate in bounded slices. Keep server-side access checks and
   business rules; do not duplicate them blindly in a new UI.
3. **Deliver offline viewing in that same frontend.** Cache startup assets with a
   service worker and persist structured list data locally (normally IndexedDB).
   Use the same rendering path online and offline rather than a separate shell.
4. **Add offline editing.** Persist local operations, retry them safely, synchronize
   on reconnect/reopen, and expose pending/failed/conflicting changes. Do not rely
   on iPhone background synchronization while the app is closed.

Each stage needs its own agreed acceptance checks before implementation. Offline
viewing can ship before editing; it need not wait for a complete sync engine.

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
- [ ] Guided Svelte basics walkthrough (see Learning approach).
- [ ] Agree prototype/API/local-data acceptance criteria.
- [ ] Validate the prototype on the actual iPhone and exercise two-device sync.
- [ ] Implement online frontend migration in separately approved slices.
- [ ] Implement and verify offline viewing.
- [ ] Implement and verify offline editing and synchronization.
