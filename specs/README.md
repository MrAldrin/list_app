# Backend port: intended behavior

These Allium specs describe what users and browsers must see after the port.
They do not say how to build the new server. Source links point to the reference
implementation. The owner approved the differences below in `lr-5g6.2`.

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

## Approved differences from the reference

| Area | Port | Python app |
| --- | --- | --- |
| Sign-in | A temporary server failure does not use a room sign-in attempt. | The failed attempt uses a slot. |
| Retry | Match fields the request actually sent. An omitted due field is not an explicit clear. The queue resends the saved request unchanged. | Replay compares the validated body and can treat an omitted date and a clear as the same. |
| Offline | After remote loss of room access, sign in again and choose **Send** or **Discard**. Sign-in does not send waiting edits. | The browser queue applies this hold on explicit sign-out, not confirmed remote loss of access. |
| Sharing | A share link can replay only answers for its own list. Room and share views of that list can share answers. | Replay checks the room and validated body, not the link's list. |

The [API docs](../docs/api.md) give the exact request and response details.
Run `allium check specs` and `allium analyse specs` from the repository root.
