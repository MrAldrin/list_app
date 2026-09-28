# Staged frontend migration for offline use

## Status and scope

Direction agreed with the owner; implementation is deferred and requires explicit
approval. Continue small improvements to the current app in the meantime.
See [experiment findings](../docs/offline-findings.md) for the rollback report,
evidence and limitations. The current shipped architecture remains NiceGUI.

## Target

Use a browser-side frontend that can run without the Python server. Keep Python
for server-side business rules, authorization and API endpoints; retain SQLite
and Railway unless a separate requirement justifies changing them. Framework
selection (for example React, Vue or Svelte) is unresolved. Native iPhone packaging
is not a prerequisite.

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
- [ ] Choose frontend and agree prototype/API/local-data acceptance criteria.
- [ ] Validate the prototype on the actual iPhone and exercise two-device sync.
- [ ] Implement online frontend migration in separately approved slices.
- [ ] Implement and verify offline viewing.
- [ ] Implement and verify offline editing and synchronization.
