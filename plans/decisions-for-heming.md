# Improvement decisions for Heming

Lifecycle: tracked

Answers to the [improvement review](improvement-ideas.md#part-3-decisions-for-you). New questions will be added here for Heming.

## 1. Feedback when checking items

**Question:** Should checking items show a separate message each time or one shared undo bar?

**Options:** Keep the current messages; replace them with one shared undo bar; or choose another approach.

**Answer:** Keep the current per-item messages. Do not build a shared undo bar.

## 2. Capital letters in item names

**Question:** Should item names keep the capital letters people type?

**Options:** Keep storing names in lowercase; or preserve capitals while treating names that differ only by case as duplicates.

**Answer:** Preserve the user's capitals and treat names such as “Milk” and “milk” as duplicates. Write the data migration plan first, then implement it.

## 3. Room sign-in lifetime

**Question:** Should room sign-ins expire after a fixed time?

**Options:** Keep the current room-token behavior; or set a lifetime, such as 180 days, after which people sign in again.

**Answer:** Keep room sign-ins as they are. No change.

## 4. Sharing a list across rooms

**Question:** Should one list appear in two rooms without accounts, or should that wait for accounts?

**Options:** Design cross-room sharing without accounts; wait until individual accounts are needed; or defer both.

**Answer:** Keep option A (no cross-room sharing) for now. Prepare written plans for B1 (one list in two rooms without accounts) and C (optional accounts) for later review; do not build either.

## 5. Feature priorities

**Question:** Which, if any, three improvement ideas matter most to you?

**Options:** Pick up to three from the [feature catalog](improvement-ideas.md#features), suggest different ideas, or choose none for now.

**Answer:** Write a short plan, then implement each of these for live review:

- Usual items: suggest frequently added items using the existing times-added count.
- Item groups: save named groups such as “Taco night” and add the whole group in one tap, skipping items already on the list.
- Aisle tags: add category tags alongside person tags, allow ordering tags, and sort/group a shopping list by that order.

Plan only: rule-based paste splitting on commas, new lines and leading quantities, with a confirmation preview. Show what it can and cannot handle; do not implement it yet. No AI in the app.

Drop the “I'm shopping” status.
