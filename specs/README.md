# Backend port: intended behavior

These Allium specs are the app's living behavior contract. They describe what
people and browsers should see, not how to build the app. The specs cite the
reference code. The owner approved the port differences below in `lr-5g6.2`
and `lr-5g6.18`.

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
- [Admin and room invitations](admin-invitations.allium): Admin sign-in is
  separate from room access. An invitation creates up to five rooms in seven
  days but does not sign anyone in.
- [Tags and checked items](tags-visibility.allium): List settings apply to
  everyone who sees the list. Hiding a checked item does not delete it.
- [Reminder settings and preview](reminder-settings.allium): Settings are
  private to the device. A preview reads a saved due date and sends nothing.
- [Install paths and old worker](install-paths.allium): A room icon opens that
  room. `/sw.js` removes the retired browser worker so the current app can load.

## Approved differences from the reference

| Area | Port | Python app |
| --- | --- | --- |
| Invitations | Show **Inactive** once a link has created five rooms. The link is already unusable. | Labels an exhausted link **Active** until expiry or revocation. |
| Sign-in | A temporary server failure does not use a room sign-in attempt. | The failed attempt uses a slot. |
| Retry | Match fields the request actually sent. An omitted due field is not an explicit clear. The queue resends the saved request unchanged. | Replay compares the validated body and can treat an omitted date and a clear as the same. |
| Offline | After remote loss of room access, sign in again and choose **Send** or **Discard**. Sign-in does not send waiting edits. | The browser queue applies this hold on explicit sign-out, not confirmed remote loss of access. |
| Sharing | A share link can replay only answers for its own list. Room and share views of that list can share answers. | Replay checks the room and validated body, not the link's list. |
| Tags | Deleting a tag clears its item assignments. A new tag starts empty. Only explicit Undo restores old assignments. | Adding the same name back makes old assignments visible again. |
| Due bell | Use the browser's time zone before reminder enrollment. | Uses Europe/Oslo when supported. |

The [API docs](../docs/api.md) give the exact request and response details.

## Maintain the specs

Start new features with Allium `elicit`. To check the specs, install the CLI
with `cargo install allium-cli --locked`, then run `allium check specs` and
`allium analyse specs` from the repository root.
