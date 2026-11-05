# B1: Share one list across rooms without accounts

Lifecycle: tracked

## Decision and scope

The owner chose to keep option A: **no cross-room sharing for now**. B1 is a
written assessment for possible later review, not a decision to build it. This
plan does not authorize implementation. B1 means one source list appears in a
second room while the rooms keep their shared-password access model. It is not
the existing public share link and not the deferred dashboard pinning idea in
[advanced sharing](advanced_sharing.md).

## Approval gate

The owner must explicitly reopen B1 from option A and authorize implementation
before anyone builds it. First, settle the room-wide permissions, revocation,
and offline decisions below. This assessment does not approve those security
choices.

## Current state

- **Implemented today:** Every list belongs to one room (`lists.room_id`). Room
  reads, writes, and the incremental feed are scoped to that room's access
  token. The browser can keep room-specific cookies. See the
  [room API](../docs/api-rooms.md#room-session), [feed](../docs/api-sync.md#reading-the-changes-feed),
  `src/api/access.py`, `src/api/ops.py`, and `src/database_crud.py`.
- **Implemented today:** A public `/share/{token}` link can edit one list, but
  it never grants room access. It has separate token reset and list-scoped feed
  behavior. See [public sharing](../docs/public-sharing.md) and
  [share links](../docs/api-sharing.md#share-links).
- **Not implemented:** No room-to-room list relation exists. The app has no
  account or per-person identity. Room-token holders share room capabilities.
- **Verified:** This assessment read the cited docs and code. No proposed B1
  behavior has been implemented or tested here.

## Assessment proposal (not approved)

If B1 is revisited, keep the list owned by its original room. Model each
additional room as an explicit link, not as copied list data or a public share
URL used as a room credential. A browser would need valid access to both rooms
to create the link. This would preserve the current rule that knowing one
room's password does not grant access to another. It would also mean that a
person who only knows the destination room's password could not link a source
list.

A link would make the list visible to **all holders of the destination room's
password**. It could not be limited to the person who created it. The
permissions for those holders remain undecided. Decide whether they can read,
check and edit items, change tags/visibility, rename the list, or delete it.
One conservative proposal is to reserve list-level management and unlinking to
the source room. This is a proposal, not an owner decision. The destination
room also needs a clear shared-list marker and a defined way to unlink the list
without deleting the source list.

### Data, feeds, and compatibility

A link table such as `(list_id, destination_room_id)` is a candidate additive
migration. Its exact constraints and unlink behavior remain for implementation
design. The difficult work is correct multi-room change tracking, not adding a
row:

- `changed_seq` and the room `seq` currently belong to the source room.
  Destination feeds must still notice item edits, tags, list settings, and
  deletions. `deletions` are currently recorded for one room. Live streams
  wake by room (`src/database_setup.py`, `src/live_updates.py`).
- A link or unlink must update the destination feed so its clients add or
  remove the list. Cursors, deletion tombstones, pruning, and stream wakeups
  must not silently miss a change. Existing per-list share sequencing is a
  possible reference, not a proven solution for multiple rooms.
- Resolve name/slug collisions with a destination room's own list. Decide what
  happens if one list is linked into several rooms or its source/destination
  room is deleted. A shared list must not expose the source room name or its
  other lists.
- All reads and writes must check the right room authorization in the same
  transaction. Choose one canonical write/retry context so queued ops do not
  apply twice when the same list is open in two rooms. Check API-version and
  old-client behavior against the [API compatibility rule](../docs/api.md#api-version).

### Offline and security

Offline pages use device-local snapshots. They keep writes in queues keyed to
a room or public share link, and revalidate room edits before sending. See
[offline use](../docs/offline-viewing.md) and the
[offline editing rules](../docs/background/offline-editing-details.md). B1
needs a distinct, documented offline identity for a linked list. A removed link,
revoked room access, or deleted source must not let stale queued edits bypass
authorization. Define how pending edits are shown and discarded or retried after
unlink. Do not let a cached snapshot or destination-room token authorize access
to the source room's other data.

A source-room password change revokes its room tokens but currently leaves its
public list links unchanged. Decide separately whether a B1 link would survive
a source password change. Do not assume that rotating a room password revokes
cross-room access. The server administrator can already read the database. B1
does not change that boundary.

## Examples and limitations

- If Alice's browser has valid access to rooms A and B, it may be able to link
  A's “Groceries” list into B. Household members who know B's shared password
  would then receive whatever permissions the owner approves.
- A partner who knows only B's password cannot link a list from A under the
  two-room-token proposal. Accounts might change that later, but are not part of
  B1.
- A public `/share/{token}` link remains a separate, single-list bearer link.
  It does not become a room link or let its holder manage B.
- Password sharing is room-wide, not individual. B1 alone cannot identify who
  linked, edited, or removed the list. It also cannot remove just one person.

## Tests required before calling a future implementation verified

Cover the migration and link/unlink lifecycle. Test access with source-only,
destination-only, both-room, stale, and revoked credentials. Test every
permitted and forbidden list/item operation, name conflicts, and list/room
deletion. Confirm that neither source-room details nor unrelated lists leak.
Exercise destination feed cursors, item/list deletions, pruning, live updates,
and reset/reconnect. Test offline edits before and after unlink, queue retry
identity, duplicate sends, and existing public-share behavior. Add browser
coverage for the shared-list marker and its actions. These are test
recommendations, not tests run by this plan.

## Questions for Lead

1. Is B1 worth reopening later, or should option A remain the standing choice?
2. If reopened, what can destination-room members do, and who may create or
   remove a link? Is room-wide access acceptable?
3. Should changing the source room password revoke its cross-room links, or must
   the source room remove each link explicitly?
4. What should happen on list-name collision, and how should shared lists be
   distinguished in navigation?
5. What is the expected offline behavior for queued edits after unlink or room
   access revocation?

## Progress

- [x] Read the current sharing, room authorization, feed, and offline contracts
  and the existing sharing assessment.
- [ ] Lead reviews the assessment and decides whether B1 remains deferred.
- [ ] No implementation is authorized by this plan.
