# Offline use

Saved data opens without a network. Edits made offline are kept on the phone
and sent when the connection is back.

Offline editing is built and tested locally. It awaits owner review (Gate C)
and is not deployed. Plan: [offline editing](../plans/offline-editing.md).
Mechanics: [offline editing details](background/offline-editing-details.md).
Pending checks: [backlog](../plans/backlog.md).

## What works offline

- Rooms, lists and share links you opened online are saved on the phone. Offline
  they open from that copy.
- Edits work there: add, tick, quantity, edit, tags, delete and undo, hide-done
  setting, rename and delete a list, rename the room. The change shows at once,
  with a dot until it is sent.
- Needs a connection: creating a list, changing the password, deleting a room,
  showing or resetting a share link, signing in or out, admin and invitations.
  These controls are disabled with "Needs a connection".
- While offline, the page says: "Offline — changes are saved on this phone and
  sent when you're back online." If changes wait, it also gives their count.

## Waiting changes

- Changes are sent in order, after the app confirms access. The check runs when
  the app opens, when the connection returns and when the app comes back to the
  screen. There is no background sync.
- Changes stay on the phone until they are sent, and a reload or closing the app
  keeps them. Where the browser cannot store them, they live in the page only,
  and a reload loses them.
- Changes older than 30 days are held. You choose Send all or Discard each.

## Merging with other devices

Changes merge when they can:

- Two +1 taps add up. Two ticks, or the same tag added twice, end in one result.
- Adding an item that someone else added keeps one item. Later changes to your
  copy go to that item.
- A change is refused when someone else changed the same thing in a different
  way, when the item or list was deleted, or when a list name is taken.

## Not saved

- A refused change that waited does not show a toast. The banner "N changes
  were not saved" opens a sheet that says what and why.
- Actions: Dismiss, or Dismiss all. A change refused because someone else
  changed it also has "Save mine anyway", which sends it again on the current
  version.
- The list is kept in the page only. A reload clears it, and refused changes
  are not sent again.

## Access gone

- If the room password changes, or a share link is reset, while changes wait,
  the banner says "N changes can't be sent."
- For a room, sign in again: the password prompt sends the waiting changes.
- For a reset share link, the only action is Discard all.

## Sign-out and room delete

- Signing out keeps waiting changes on the phone. They are sent after you sign
  in to the same room. The app asks first.
- Deleting a room discards its waiting changes. The app asks first.

## After a deploy

- A new version downloads in the background. Open pages move to it when they
  hold no unsent changes or typed text.
- If the server answers with another API version, the page stops sending
  changes and shows "A new version is available" with a Reload button. Waiting
  changes stay on the phone and are sent after Reload, onto the matching
  version. Reading continues.
- Answers without the version header count as compatible. See
  [API version](api.md#api-version).
