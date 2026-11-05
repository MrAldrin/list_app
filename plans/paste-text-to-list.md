# Rule-based paste text to a list

Lifecycle: tracked

## Decision and scope

The owner asked for a plan only: split pasted text on commas and new lines,
recognize leading quantities, and show a confirmation preview. **No AI in the
app.** This plan does not authorize implementation. Keep any parsing local in
the browser; do not send pasted messages to an AI service or another server.

## Approval gate

The owner must separately authorize implementation; the present decision is
only to prepare this plan. Confirm any `item.add` API change and partial-success
behavior before building. No AI/parser service or raw-paste upload is approved.

## Current state

- **Implemented today:** The app adds one item per `item.add` operation. Item
  names are trimmed, stored lowercase, and limited to 100 characters. A new
  item starts with quantity 1; quantity changes use a separate delta operation.
  See the [operation contract](../docs/api-lists-items.md#operation-types),
  `src/api/ops.py`, and `frontend/src/lib/data/index.ts`.
- **Implemented today:** Each write is an individual operation, with offline
  queueing, replay, duplicate handling, and a per-item “not saved” path. There
  is no atomic multi-item API operation. See [offline use](../docs/offline-viewing.md)
  and [offline editing details](../docs/background/offline-editing-details.md).
- **Not implemented:** There is no paste parser, bulk-add endpoint, or preview.
- **Verified:** This assessment read the cited docs and code. No parser or
  paste flow has been implemented or tested here.

## Proposed first version (not approved)

Use a plain-text input and a pure, deterministic client-side parser. A
confirmation screen should show every parsed item and its quantity before any
write is queued. Cancel adds nothing. A first narrow rule set could be:

1. Split on commas and line breaks; trim outer whitespace and ignore empty
   pieces.
2. Recognize a positive whole number followed by whitespace as a quantity,
   such as `2 apples`. Also accept `2x apples` and `2× apples`, with an optional
   space before the marker, as `2 apples`. Keep the remaining text as the item
   name.
3. Treat text that does not match those narrow quantity forms as the complete
   item name, rather than guessing. Use the existing name normalization,
   duplicate, length, and add/restore rules when the user confirms.

The preview should make parsing visible (for example, `apples — quantity 2`).
It should not imply that the parser understands recipe meaning. It can show item
rows in the order they will be submitted. Whether people can edit/remove
preview rows is an open UX decision. Render pasted text as text, not HTML. Do
not persist the raw paste. Confirmed item operations can use the existing local
queue.

### Quantity interface and partial results

The current `item.add` does not accept an initial quantity. A future
implementation must resolve this before it can faithfully add a parsed item
with its requested quantity. The cleaner candidate is an optional initial
quantity on `item.add`. The candidate would carry it through API validation,
client types, optimistic state, and offline queue validation. A second
candidate is to add then send a quantity delta. This creates a dependent two-op
sequence and makes duplicate/restored items and partial failures harder to
explain. This is an interface choice, not an existing capability.

The API applies one operation at a time, so a multi-item paste is not atomic.
If some rows succeed while others are rejected, the UI must report which rows
were saved and which were not. This may happen because an item is already
active, its name is too long, or the list reaches the 1,000-item cap. The UI
must not imply that Cancel or a retry rolls back earlier writes. The per-item
queue should preserve order offline and show ordinary waiting/rejected
changes. Decide whether the preview warns about known duplicates or capacity.
Treat its snapshot as staleable; the server remains the final authority.

This work also intersects the separate approved plan to preserve typed item
capitalization with case-insensitive duplicate detection. Keep parser output
and duplicate matching on the app's shared item-name rules. Do not create a
second normalization rule. Before implementation, coordinate with the
[recorded owner decision](decisions-for-heming.md#2-capital-letters-in-item-names)
and the item-name migration plan.

## Examples and limitations

For the proposed simple parser:

| Pasted text | Preview result | Limitation shown |
|---|---|---|
| `milk, eggs` | `milk` × 1; `eggs` × 1 | Two simple comma-separated names. |
| `2 apples` | `apples` × 2 | A leading integer is a count, not a unit conversion. |
| `3x oat milk` | `oat milk` × 3 | It is not natural-language understanding. |
| `1/2 cup flour` | The whole text as one name × 1 | Fractions are not parsed. |
| `2 tbsp olive oil` | Could become `tbsp olive oil` × 2 | Units are not modeled; this parse may mislead. |
| `one apple` | The whole text as one name × 1 | Number words are not parsed. |
| `sauce, extra` | Two names | Commas inside a name are ambiguous; quoted CSV and recipe syntax are out of scope initially. |

Other limits: no fractions, decimals, unit conversion, ingredient extraction,
sub-recipe parsing, comments, bullet hierarchy, or recipe directions. The app's
quantity is a positive integer, not “2 kg” or “1/2 cup”. Name length, maximum
paste size/row count, numeric quantity bounds, repeated names in one paste,
and collision with existing active or checked items need explicit limits and
clear preview results. These limitations should be visible before confirming,
not hidden behind a promise to parse recipes.

## Tests required before calling a future implementation verified

Unit-test the parser for comma/newline/CRLF separators, whitespace, blank
pieces, simple and malformed quantity prefixes, zero/fraction/decimal/unit
examples, commas within text, and name-length boundaries. Test the preview with
screen-reader labels, keyboard navigation, cancel, and confirmation on
mobile-sized layouts. Test quantity initialization and duplicate/restore
behavior through normal operations, offline queue replay and uncertain retries,
server rejection, partial-success reporting, and the existing 1,000-item limit.
If the API changes, test legacy clients and API-version behavior. Verify that no
raw paste leaves the browser before confirmation and that no AI or external
parser is called. These are recommendations, not tests run by this plan.

## Questions for Lead

1. Which quantity prefix should be supported exactly (`2 apples`, `2x apples`,
   both, or another syntax)? Should an unrecognized numeric prefix stay intact
   as the item name?
2. Should the preview allow editing/removing rows, and should known duplicates
   be skipped, flagged, or submitted to the usual add rules? If a checked item
   is restored, should the parsed quantity replace its old quantity or keep it?
3. Is adding the initial quantity to `item.add` acceptable, or should this stay
   within current operations despite the dependent add-then-delta behavior?
4. Is partial success acceptable for a batch paste? If so, how should saved and
   rejected rows be summarized? If not, a transactional bulk endpoint needs its
   own idempotency, conflicts, and offline design.
5. What input size, row count, and quantity limits should the first version
   enforce?

## Progress

- [x] Read the item write contract, quantity behavior, offline queue rules, and
  owner decisions.
- [ ] Lead reviews parsing grammar, quantity interface, and partial-success UX.
- [ ] No implementation is authorized by this plan.
