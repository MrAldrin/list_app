# Deferred idea: Cross-room list pinning

## Status

Deferred. This is not part of the current MVP and is separate from the public
list-link security work.

## Concept

A person with access to their own room could pin a public list from another
room to their room dashboard for convenience. The list would remain public by
link; pinning would not grant access to the source room or its other lists.

## Boundaries

- The canonical public-link and token design lives in
  [`public_list_share_tokens.md`](public_list_share_tokens.md). This document
  does not define another token format or sharing route.
- Adding or removing a pin requires valid authorization for the destination
  room.
- The current app has shared room passwords, not individual owners or member
  accounts. The authorization rules for pin management must be decided before
  implementation.
- A public-link visitor who has no authorized destination room cannot pin the
  list.

## Possible workflow

1. A person opens a valid public list link.
2. If they have an authorized room, the app offers to pin the list there.
3. The person confirms the destination room.
4. The room dashboard shows the pinned list with a clear shared-list marker.
5. The person can remove the pin without affecting the source list or its
   public link.

## Data model to revisit

A `room_shared_lists` table could associate a destination room with a shared
list. Revisit uniqueness, deleted-room/list behavior, and whether a list may
be pinned more than once before implementation.

## Open questions

- Should a pinned list be editable, read-only, or follow the current public
  link behavior?
- How should a user choose among multiple authorized rooms?
- What happens when the public token is rotated or the source list is deleted?
- What dashboard and real-time refresh behavior is useful enough to justify
  this feature?
