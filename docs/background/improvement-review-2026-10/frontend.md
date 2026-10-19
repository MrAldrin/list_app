# Frontend report (condensed by orchestrator from agent message)
Checks: svelte-check/eslint/prettier clean; vitest 592/593 (offline-integration.test.ts:1505 flaky, vi.waitFor 1s default). ~12.9k lines non-test; ~94 KB gzip JS total.
1. [M,S,risk M] Whole room snapshot rewritten to IndexedDB on every refresh, even unchanged (room-store.svelte.ts:397-404, applyFeed 318-336 true for equal seq; index.ts:849-875; snapshot-store.ts:329-347). Needs savedAt rule decision.
2. [M,S-M] Error model repeated/loosely typed: room-store.svelte.ts:710-781 opSettled/opFailed dupes, fallback text differs vs result.ts:11; result.ts maps all non-API errors to 'network'; ActionResult.code is string though RejectionCode exists (types.ts:197-207). Fix: ActionCode union + settle() helper.
3. [M,L] RoomHandle 900-line class (index.ts:186-1084): extract room-session.ts and room-writes.ts. After #2.
4. [M,M] RoomStore mixes 4 concerns: split Not-saved list, op tracking.
5. [M,S-M] ListView.svelte: visible-items pipeline in component (82-91) -> pure fn in items.ts; 3 duplicate showUndoToast blocks; `now` used before declared.
6. [M,S] Tap targets small: ItemRow.svelte:238 qty buttons 20x28, :274 tag buttons 26x26, row 36px; --touch is 44px (app.css:45).
7. [L-M] Duplicated status UI: LoadError condition x2, "Needs a connection" pattern x5, list/share routes duplicate .problem + effect, SavedChanges name lookup.
8. [L,S,risk M] write-queue.ts repeats filter 4x; IndexedDB re-read per send.
9. [M,S-M] Test reliability: flaky test; fakeApi defined 3x, memoryStorage 2x; offline-integration.test.ts 1859 lines.
10. [L-M,S] a11y: generic "Dismiss"/"Discard" labels; global id focus.
11. [L] Encapsulation: direct savedAt writes, SvelteMap for non-rendered maps.
12. [L] CreateRoomForm own busy flag w/o try/finally; password length check x3.
13. [L,S] Dead code: events.ts:236-240 sync branches; index.ts:925-941 duplicate branches; wrong doc comment index.ts:167; double import DeleteRoomDialog.svelte:6,8.
14. [L] Two files named service-worker.ts; mixed import styles; copy in 5 places.
Top 3: #2, #6, #9. Effect/TanStack: no — hard parts are domain logic (queue, projection, rebase); take ideas in plain TS.
