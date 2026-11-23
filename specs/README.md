# Backend port: behavior to review

These four Allium drafts describe what users and browsers see today. They do
not say how to build the new server. Read this page first on a phone. Each
spec links behavior to its source code.

- [Rooms and sign-in](room-access.allium): A room password opens that room.
  Admin sign-in is separate. Changing a room password ends old room sessions.
- [Items and op replay](item-operations.allium): A retry returns the original
  answer. Quantity changes add up. An edit cannot silently overwrite a newer
  change. Adding a checked item reopens it instead of making a copy.
- [Sync and offline edits](sync-offline.allium): A live signal tells the page
  to fetch changes. Offline edits wait on the device until the app can send
  them in order. The app shows which edits it could not save.
- [Public links](public-sharing.allium): A link opens one list, not its room.
  Resetting the link cuts off the old page, including its waiting edits.

## Open questions for owner review

1. **Sign-in.** Should a temporary server failure use one of the room's
   sign-in attempts? It does today.
2. **Retry.** The server matches a retry with its saved answer. For item
   edits, it currently matches a missing date with an explicit date clear.
   Should the port keep this behavior for compatibility?
3. **Offline.** After another device resets the room password, should the app
   wait for **Send** or **Discard** after sign-in? The offline guide says yes.
   The current queue sets this hold on explicit sign-out, not on remote loss
   of access.
4. **Sharing.** Saved answers currently match the room, not the share link's
   list. Should a share link replay only answers for its own list? Should a
   room view and a share view of the same list still share saved answers?

The [API docs](../docs/api.md) give the exact request and response details.
Run `allium check specs` and `allium analyse specs` from the repository root.
