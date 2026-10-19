# Backend report (condensed by orchestrator)
pytest 1360 in 39s; ruff, ty clean.
1. [H,S,risk M] bcrypt (~190ms) runs inside global _DB_LOCK: database_crud.py:938-955 (sign-in), 1046 (change pw), 1059-1062 (delete room). Rate limit per slug (api/sign_in_limit.py:24) -> random slugs bypass; ~5 req/s freezes all DB work. Fix: read txn, bcrypt outside lock, write txn re-checking authorization_version/hash; global sign-in bucket (~30 fails/min).
2. [M,S,L] No-op writes bump room seq -> false changed_meanwhile conflicts. update_item_done_locked (database_crud.py:443-460), update_list_visibility_settings_locked (171-175); triggers database_setup.py:268-320; _check_base_seq ops.py:362-374. Fix: WHERE ... IS NOT ? / early return; test in tests/test_api_conflicts.py. VERIFIED scenario.
3. [M,S] Typing: `db: Any` (database_setup.py:652) hides 78 execute calls; lastrowid int|None at database_crud.py:282,342,393,560, room_invitations.py:39; missing return annotations (get_lists, get_rooms, get_room_details_by_slug, create_room, init_database).
4. [M,M] database_crud.py 1098 lines, 8 concerns; room_invitations.py imports _DB_LOCK/db directly. Split by area after 3.
5. [L-M,S] Three room-creation paths with different slug formats (crud make_slug, invitations token_urlsafe(18), default room); admin.py:140 duplicate pw check, 142 extra re-read.
6. [L,S] Dead/test-only: get_lists (only tests), live_updates _listeners seam, wake_streams(None).
7. [L,S] Missing index deletions(uid) (uid_in_use_locked full scan); migration 11.
8. Full snapshot 6000 items 15ms under lock; fine now.
9. SSE fan-out negligible at 5 users; events.py room/share stream code near-duplicate.
10. 30-day processed-op prune: quantity_delta retry after 31 days double-applies; accepted trade-off.
11. Small dupes: ops.py _item_name/_display_name/_tag; two ISO formatters; _NOW_SQL == _NOW_TEXT.
12. ops.py 696 lines: split models/handlers when next touched.
13-15. Skip: JSON tag normalization (nothing queries tags; close backlog item), WAL (one conn+lock; doc says keep off), Python package (high churn).
Top 3: #1, #2, #3+#6.
